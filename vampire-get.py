#!/usr/bin/env python

import pexpect
from ConfigParser import ConfigParser
from optparse import OptionParser
import os
import re
import json
from zipfile import ZipFile
import StringIO
from pprint import pprint
import tempfile
import logging


reDRIVER_IGNORE = re.compile(r'Server does not support environment .*$')
reDRIVER_ARCH = re.compile(r'\[(?P<arch>Windows .*)\]$')
reDRIVER_START = re.compile(r'Printer Driver Info 1:$')
reDRIVER_NAME = re.compile(r'Driver Name: \[(?P<name>[-_A-Za-z0-9 ]+)\]$')
reDRIVER_FILE_START3 = re.compile(r'Printer Driver Info 3:$')
reDRIVER_FILE_VERSION = re.compile(r'Version: \[3\]$')
reDRIVER_FILE_ITEM = re.compile(r'(?P<key>.+): \[(?P<value>.+)\]$')
reDRIVER_PATH = re.compile(r'\\\\(?P<name>[^\\]+)\\(?P<share>print\$)\\'\
			'(?P<path>.*)$')

DRIVER_KEYS = ['Version','Architecture','Driver Path', 'Datafile', 
	'Configfile', 'Helpfile', 'Driver Name', 'Monitorname',
	'Defaultdatatype'
	]
DRIVER_EXTRA = ['Dependentfiles']

DRIVER_FILES = ['Driver Path', 'Configfile', 'Helpfile', 'Datafile',
	'Dependentfiles']

class SrcDriver(object):
	'''
		Printer driver wrapper
	'''
	def __init__(self, host, printer, driverName):
		self._host = host
		self.printer = printer
		self.driverName = driverName
		self._driverInfo = None
		self._driverArchive = None

	def __repr__(self):
		return "<SrcDriver '%s' id=0x%x>" % (self.driverName, id(self))

	@property
	def driverInfo(self):
		if self._driverInfo is not None:
			return self._driverInfo
		self._driverInfo = self._loadDriverInfo()
		return self._driverInfo

	@property
	def driverArchive(self):
		if self._driverArchive is not None:
			return self._driverArchive
		self._driverArchive = self._loadDriverArchive()
		return self._driverArchive

	@property
	def archiveName(self):
		retv = "%s---%s.zip" % \
			(self.driverInfo['Driver Name'],
			self.driverInfo['Architecture'])
		return retv.replace(' ','_')

	def saveArchive(self, filename=None, directory=None):
		if directory is None:
			directory = os.getcwd()
		if filename is None:
			filename = self.archiveName
		target = os.path.join(directory, filename)
		open(target, 'wb').write(self.driverArchive)


	@property
	def printerName(self):
		return self.printer.name
		
	def _loadDriverInfo(self):
		cmd = self._host._prepareCommandList()
		cmd.append('''-c 'getdriver "%s" ' ''' % self.printerName)
		command = ' '.join(cmd)
		logging.info('Loading driver info for "%s"' % self.printerName)
		logging.debug('Run: %s' % command)
		output = pexpect.run(command)
		#
		driverInfo = {}
		logging.info('Parsing driver info')
		for ln in output.split('\n'):
			if not ln.strip(): continue
			ln = ln.strip()
			if reDRIVER_FILE_START3.match(ln): continue # 
			if reDRIVER_ARCH.match(ln): continue # 
			if reDRIVER_FILE_ITEM.match(ln): 
				m = reDRIVER_FILE_ITEM.match(ln)
				k,v = m.group('key'), m.group('value')
				if k in DRIVER_KEYS:
					assert k not in driverInfo, k
					driverInfo[k] = v
				elif k in DRIVER_EXTRA:
					if k not in driverInfo:
						driverInfo[k] = [v]
					else:
						driverInfo[k].append(v)
				else:
					assert k in DRIVER_KEYS or \
						k in DRIVER_EXTRA, k
				continue
			assert reDRIVER_IGNORE.match(ln), ln
		return driverInfo

	def _loadDriverArchive(self):
		def _filePath(unc_path):
			m = reDRIVER_PATH.match(unc_path)
			assert m, unc_path
			return m.group('path')
			
		logging.info('Getting driver files for "%s"' % self.driverName)
		files = {}
		for k,v in self.driverInfo.items():
			if k not in DRIVER_FILES: 
				continue
			if type(v) == type(''):
				v = [v]
			for fname in v:
				fname = _filePath(fname)
				logging.debug('Downloading file "%s"' % fname)
				filedata = self._host._downloadFile(fname)
				files[fname] = filedata
		# prepare ZIP
		logging.debug('Creating driver archive file')
		archive_file = StringIO.StringIO()
		archive = ZipFile(archive_file, 'a')
		for fname in files:
			target_name = fname.lower().replace('\\','/')
			archive.writestr(target_name, files[fname])

		# append JSON
		logging.debug('Creating driver JSON file')
		driver_info = {}
		for k,v in self._driverInfo.items():
			if k not in DRIVER_FILES:
				driver_info[k] = v
				continue
			if type(v) == type(''):
				driver_info[k] = _filePath(v).lower()
			else:
				driver_info[k] = \
					[_filePath(l).lower() for l in v]
		json_info = json.dumps(driver_info, indent=4)
		archive.writestr('driverinfo.json', json_info)
		archive.close()
		logging.debug('Archive file created')
		#
		return archive_file.getvalue()
		
			

class SrcPrinter(object):
	'''
		Printer wrapper. 
	'''
	def __init__(self, path, name, driverName, comment, host):
		self.path = path
		self.name = name
		self.driverName = driverName
		self.comment = comment
		self._driver = None
		self.host = host

	@staticmethod
	def fromDict(a_dict, host):	
		assert 'name' in a_dict, a_dict
		assert 'description' in a_dict, a_dict
		assert host is not None
		name = a_dict['name'].split('\\')[-1]
		driverName = a_dict['description'].split(',')[1]
		return SrcPrinter(
			path=a_dict['name'],
			name=name,
			driverName = driverName, 
			comment = a_dict['comment'],
			host=host)

	def __repr__(self):
		return "<SrcPrinter '%s' [%s] host=%s id=0x%x>" % (self.name, self.driverName, 
				self.host.name, id(self))

	@property
	def driver(self):
		if self._driver is not None:
			return self._driver
		self._driver = SrcDriver(host=self.host, printer=self, driverName=self.driverName)
		return self._driver

class SrcHost(object):
	def __init__(self, host, options):
		self.host = host
		self.options = options
		self._printers = None
		self._drivers = None

	@property
	def name(self): return self.host

	@property
	def printers(self):
		if self._printers is None:
			self._printers = self._loadPrinterList()
		return self._printers

	def drivers(self):
		if self._drivers is None:
			self._drivers = self._loadDriverList()
		return self._drivers
	
	def _loadPrinterList(self):
		logging.info('Enumerating printers')
		cmd = self._prepareCommandList()
		cmd.append('-c "enumprinters"')
		command = ' '.join(cmd)
		logging.debug(command)
		output = pexpect.run(command)
		#
		values = {}
		printers = []
		logging.debug('Parsing response')
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
				a_printer = SrcPrinter.fromDict(values, 
							host=self)
				printers.append(a_printer)
				values = {}
		logging.debug('Printer list created')
		return printers

	def _loadDriverList(self):
		logging.info('Enumerating drivers')
		cmd = self._prepareCommandList()
		cmd.append('-c "enumdrivers"')
		command = ' '.join(cmd)
		logging.debug(command)
		output = pexpect.run(command)
		#
		logging.debug('Parsing response')
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
				a_driver = SrcDriver(host=self, name=name)
				drivers[name] = a_driver
				continue
			assert reDRIVER_IGNORE.match(ln), ln
		return drivers.values()

	def _downloadFile(self, file_name):
		#
		cmd = ['smbclient', '//%s/print$' % self.host]
		if self.options.source_address:
			cmd.append('-I %s' % self.options.source_address)
		if self.options.source_user and self.options.source_password:
			cmd.append('-U "%s"%%"%s"' % 
				(self.options.source_user,
				 self.options.source_password))
		_,output_name = tempfile.mkstemp()
		cmd.append("-E -c 'get \"%s\" \"%s\"" % (file_name, output_name))
		#
		command = ' '.join(cmd)
		pexpect.run(command)
		output = open(output_name, 'rb').read()
		os.unlink(output_name)
		return output

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
	parser.add_option('-v', '--verbose', action='count', dest='verbosity',
				metavar='LOG_LEVEL',
				help='Increase verbosity (multiple times allowed)')
	# set defaults
	parser.set_defaults(**dict(config.items('config')))

	# parse
	opts,args = parser.parse_args()
	
	# set verbosity level	
	log_level = logging.WARNING
	if opts.verbosity == 1:
		log_level = logging.INFO
	elif opts.verbosity >= 2:
		log_level = logging.DEBUG
	logging.basicConfig(level=log_level)
	return opts, args

	

def main():
	options,args = parseArguments()
	src = SrcHost.fromOptions(options)
	printers = src.printers
	pprint(printers)
	for pr in printers:
		print 'Loading driver for %s' % pr.name
		dr = pr.driver
		print 'Loading driver files %s' % dr.driverName
		dr.saveArchive()

		



if __name__ == '__main__':
	main()
