#!/usr/bin/env python

import pexpect
from ConfigParser import ConfigParser
from optparse import OptionParser
import re
reDRIVER_IGNORE = re.compile(r'Server does not support environment .*$')
reDRIVER_ARCH = re.compile(r'\[(?P<arch>Windows .*)\]$')
reDRIVER_START = re.compile(r'Printer Driver Info 1:$')
reDRIVER_NAME = re.compile(r'Driver Name: \[(?P<name>[-_A-Za-z0-9 ]+)\]$')
reDRIVER_FILE_START3 = re.compile(r'Printer Driver Info 3:$')
reDRIVER_FILE_VERSION = re.compile(r'Version: \[3\]$')
reDRIVER_FILE_ITEM = re.compile(r'(?P<key>.+): \[(?P<value>.+)\]$')

DRIVER_KEYS = ['Version','Architecture','Driver Path', 'Datafile', 
	'Configfile', 'Helpfile', 'Driver Name', 'Monitorname',
	'Defaultdatatype'
	]
DRIVER_EXTRA = ['Dependentfiles']


class SrcDriver(object):
	'''
		Printer driver wrapper
	'''
	def __init__(self, name):
		self.name = name

	def __repr__(self):
		return "<SrcDriver '%s' id=0x%x>" % (self.name, id(self))

class SrcPrinter(object):
	'''
		Printer wrapper. 
	'''
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
		self._drivers = None

	def printers(self):
		if self._printers is None:
			self._printers = self.loadPrinterList()
		return self._printers

	def drivers(self):
		if self._drivers is None:
			self._drivers = self.loadDriverList()
		return self._drivers
	
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

	def loadDriverList(self):
		cmd = self._prepareCommandList()
		cmd.append('-c "enumdrivers"')
		command = ' '.join(cmd)
		output = pexpect.run(command)
		#
		drivers = {}
		for ln in output.split('\n'):
			if not ln.strip(): continue
			ln = ln.strip()
			if reDRIVER_IGNORE.match(ln): continue
			if reDRIVER_START.match(ln): continue
			if reDRIVER_ARCH.match(ln): continue # 
			if reDRIVER_NAME.match(ln):
				m = reDRIVER_NAME.match(ln)
				name = m.group('name')
				if name in drivers: continue
				a_driver = SrcDriver(name=name)
				drivers[name] = a_driver
				continue
			assert reDRIVER_IGNORE.match(ln), ln
		return drivers.values()

	def loadDriverFiles(self, driver):
		cmd = self._prepareCommandList()
		cmd.append('''-c 'getdriver "%s" ' ''' % driver.name)
		command = ' '.join(cmd)
		output = pexpect.run(command)
		#
		driver = {}
		for ln in output.split('\n'):
			if not ln.strip(): continue
			ln = ln.strip()
			if reDRIVER_FILE_START3.match(ln): continue # 
			if reDRIVER_ARCH.match(ln): continue # 
			if reDRIVER_FILE_ITEM.match(ln): 
				m = reDRIVER_FILE_ITEM.match(ln)
				k,v = m.group('key'), m.group('value')
				if k in DRIVER_KEYS:
					assert k not in driver, k
					driver[k] = v
				elif k in DRIVER_EXTRA:
					if k not in driver:
						driver[k] = [v]
					else:
						driver[k].append(v)
				else:
					assert k in DRIVER_KEYS or \
						k in DRIVER_EXTRA, k
				continue
			assert reDRIVER_IGNORE.match(ln), ln
		return driver

			

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
	first_driver = src.drivers()[0] 
	print first_driver
	print src.loadDriverFiles(first_driver)

		



if __name__ == '__main__':
	main()
