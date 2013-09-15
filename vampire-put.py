#!/usr/bin/env python

import pexpect
from ConfigParser import ConfigParser
from optparse import OptionParser
import os
import re
import json
from zipfile import ZipFile
import tarfile
import StringIO
from pprint import pprint
import tempfile
import logging
import glob
import time


DRIVER_KEYS = ['Version','Architecture','Driver Path', 'Datafile', 
	'Configfile', 'Helpfile', 'Driver Name', 'Monitorname',
	'Defaultdatatype'
	]
DRIVER_EXTRA = ['Dependentfiles']

DRIVER_FILES = ['Driver Path', 'Configfile', 'Helpfile', 'Datafile',
	'Dependentfiles']

class DestinationHost(object):
	def __init__(self, host, options):
		self.host = host
		self.options = options

	@property
	def name(self): 
		return self.host

	def uploadArchive(self, archive_name):
		#
		logging.info('Uploading %s' % archive_name)
		cmd = ['smbclient', '//%s/print$' % self.host]
		if self.options.destination_address:
			cmd.append('-I %s' % self.options.destination_address)
		if self.options.destination_user and self.options.destination_password:
			cmd.append('-U "%s"%%"%s"' % 
				(self.options.destination_user,
				 self.options.destination_password))
		#
		cmd.append("-E -c 'tar x %s" % archive_name)
		#
		command = ' '.join(cmd)
		logging.debug(command)
		output = pexpect.run(command)
		logging.debug('GOT:\n%s' % output)

	def registerDriver(self, cmd_line):
		cmd = self._prepareCommandList()
		cmd.append("-c '%s'" % cmd_line)
		command = ' '.join(cmd)

		logging.debug(command)
		output = pexpect.run(command)
		print output


	def _prepareCommandList(self):
		cmd = ['rpcclient', self.host]
		if self.options.destination_address:
			cmd.append('-I %s' % self.options.destination_address)
		if self.options.destination_user and self.options.destination_password:
			cmd.append('-U "%s"%%"%s"' % 
				(self.options.destination_user,
				 self.options.destination_password))
		return cmd
		

	@staticmethod
	def fromOptions(options):
		host = options.destination_hostname
		return DestinationHost(host=options.destination_hostname, options=options)

	def __repr__(self):
		return "<DestinationHost '%s' id=0x%x>" % (self.host, id(self))
		

def parseArguments():
	config = ConfigParser()
	config.read(['vampire.ini'])

	parser = OptionParser()
	parser.add_option('-T', '--destination-host', dest='destination_hostname', 
				metavar='HOSTNAME',
				help='Host to copy drivers to')
	parser.add_option('-A', '--address', '--destination-address', dest='destination_address', 
				metavar='IP_ADDRESS',
				help='IP address of destination host')
	parser.add_option('-U', '--user', '--destination-user', dest='destination_user', 
				metavar='USERNAME',
				help='User for destinationhost')
	parser.add_option('-P', '--password', '--destination-password', dest='destination_password', 
				metavar='PASSWORD',
				help='Password for destination host')
	parser.add_option('-v', '--verbose', action='count', dest='verbosity',
				metavar='LOG_LEVEL',
				help='Increase verbosity (multiple times allowed)')

	parser.add_option('-g', '--go', dest='go',
				help='Load all *.zip files and upload them')
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

class DriverFile(object):
	def __init__(self,sourceName):
		self._driverInfo = None
		self._archive = self._load(sourceName)

	def _load(self, sourceName):
		logging.info("Loading %s" % sourceName)
		archive = ZipFile(sourceName)
		driverInfo = archive.open('driverinfo.json')
		di = self._driverInfo = json.loads(driverInfo.read())
		logging.info("Driver present '%s' '%s'" % (
				di['Driver Name'],
				di['Architecture']))
		return archive

	@staticmethod
	def _archName(f):
		arch = f.split('/')[0]
		base = f.split('/')[-1]
		return '%s/%s' % (arch, base)
		

	def upload(self, host):
		file_list = []
		dinfo = self._driverInfo
		for key in DRIVER_FILES:
			if type(dinfo[key]) != type([]):
				file_list.append(dinfo[key])
			else:
				file_list.extend(dinfo[key])
		file_list = [str(i) for i in file_list]
		#
		_,temp_name = tempfile.mkstemp()
		archive = tarfile.open(temp_name, 'w')
		for fname in file_list:
			a_file = self._archive.open(fname)
			file_data = a_file.read()
			#
			tmp_file = StringIO.StringIO(file_data)
			#
			tarinfo = tarfile.TarInfo(self._archName(fname))
			tarinfo.size =  len(file_data)
			archive.addfile(tarinfo, tmp_file)
		archive.close()
		host.uploadArchive(temp_name)
		os.unlink(temp_name)
		#
# Usage: adddriver <Environment> \
#	<Long Printer Name>:<Driver File Name>:<Data File Name>:\
#	<Config File Name>:<Help File Name>:<Language Monitor Name>:\
#	<Default Data Type>:<Comma Separated list of Files> \
#		[version]

	@staticmethod
	def _baseName(f):
		if type(f) == type([]):
			return [DriverFile._baseName(g) for g in f]
		return f.split('/')[-1]


	def register(self, host):
		_strip = self._baseName
		data = [(k,_strip(v)) for k,v in self._driverInfo.items()]
		data = dict(data)
		dependent = ','.join(data['Dependentfiles'])
		data['Dependentfiles'] = dependent
		data['version'] = int(time.time())
		cmd_line = 'adddriver "%(Architecture)s" '\
			'"%(Driver Name)s":%(Driver Path)s:%(Datafile)s:'\
			'%(Configfile)s:%(Helpfile)s:%(Monitorname)s:'\
			'%(Defaultdatatype)s:%(Dependentfiles)s '\
			'%(Version)s' % data
		cmd_line = cmd_line.replace('/','\\')
		host.registerDriver(cmd_line)

			

def main():
	options,args = parseArguments()
	destination = DestinationHost.fromOptions(options)
	if options.go:
		files = glob.glob("*.zip")
	else:
		print 'Enter zip.files to upload'
		raise SystemExit
	for fname in files:
		driver = DriverFile(sourceName=fname)
		driver.upload(host=destination)
		driver.register(host=destination)
		
if __name__ == '__main__':
	main()
