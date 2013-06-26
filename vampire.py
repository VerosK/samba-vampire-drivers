#!/usr/bin/env python

import pexpect
from ConfigParser import ConfigParser
from optparse import OptionParser

class SrcPrinter(object):
	pass

class SrcHost(object):
	def __init__(self, host, options):
		self.host = host
		self.options = options
		self._printers = None

	def printers(self):
		if self._printers is None:
			self._printers = self.loadPrinterList()
		return self._printers
	
	def loadPrinterList(self):
		cmd = self._prepareCommandList()
		cmd.append('-c "enumprinters"')
		command = ' '.join(cmd)
		output = pexpect.run(command)
		for ln in output.split('\n'):
			if not ln.strip(): continue

	def _prepareCommandList(self):
		cmd = ['rpcclient', self.host]
		if self.options.source_address:
			cmd.append('-I %s' % self.options.source_address)
		if self.options.source_user and self.options.source_password:
			cmd.append('-U "%s"%%"%s"' % 
				(self.options.source_user,
				 self.options.source_password))
		return cmd
		
		

	@staticmethod
	def fromOptions(options):
		host = options.source_hostname
		return SrcHost(host=options.source_hostname, options=options)

	def __repr__(self):
		return "<SrcHost '%s' id=0x%x>" % (self.host, id(self))
		

def parseArguments():
	config = ConfigParser()
	config.read(['vampire.ini'])

	parser = OptionParser()
	parser.add_option('-s', '--host', '--source-host', dest='source_hostname', 
				metavar='HOSTNAME',
				help='Host to copy drivers from')
	parser.add_option('-a', '--address', '--source-address', dest='source_address', 
				metavar='IP_ADDRESS',
				help='IP address of source host')
	parser.add_option('-u', '--user', '--source-user', dest='source_user', 
				metavar='USERNAME',
				help='User for source host')
	parser.add_option('-p', '--password', '--source-password', dest='source_password', 
				metavar='PASSWORD',
				help='Password for source host')

	# set defaults
	parser.set_defaults(**dict(config.items('config')))

	return parser.parse_args()
	

def main():
	options,args = parseArguments()
	src = SrcHost.fromOptions(options)
	print src
	print src.printers()

		



if __name__ == '__main__':
	main()
