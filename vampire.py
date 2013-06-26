#!/usr/bin/env python

import pexpect
from ConfigParser import ConfigParser
from optparse import OptionParser

class SrcDriver(object);
	def __init__(self):
		pass

class SrcPrinter(object):
	def __init__(self, path, name, driver, comment):
		self.path = path
		self.name = name
		self.driver = driver
		self.comment = comment

	@staticmethod
	def fromDict(a_dict):	
		assert 'name' in a_dict, a_dict
		assert 'description' in a_dict, a_dict
		name = a_dict['name'].split('\\')[-1]
		driver = a_dict['description'].split(',')[1]
		return SrcPrinter(
			path=a_dict['name'],
			name=name,
			driver = driver, 
			comment = a_dict['comment'])

	def __repr__(self):
		return "<SrcPrinter '%s#%s' id=0x%x>" % (self.name, self.driver, id(self))

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
		#
		values = {}
		printers = []
		for ln in output.split('\n'):
			if not ln.strip(): continue
			parts = ln.strip().split(':',1)
			key = parts[0]
			assert parts[1][0]=='[',`parts[1]`
			assert parts[1][-1]==']',`parts[1]`
			value = parts[1][1:-1]

			if key == 'flags': 
				assert len(values) == 0, values
			values[key] = value

			if key == 'comment':
				a_printer = SrcPrinter.fromDict(values)
				printers.append(a_printer)
				values = {}
		return printers
			

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
