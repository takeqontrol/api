"""
Hardware interfacing for Qontrol modules.

This module lets you control Qontrol hardware modules, natively in Python. It provides 
a main Qontroller class which handles enumeration, low-level communications, sequencing, 
error-handling, and log maintenance. Subclasses of Qontroller implement module-specific 
features (e.g. DC current or voltage interfaces, positional interfaces).

Learn more, at www.qontrol.co.uk/support, or get in touch with us at
support@qontrol.co.uk. Contribute at github.com/takeqontrol/api.

(c) 2021 Qontrol Ltd.
"""

from __future__ import print_function
import serial, re, time
from collections import deque as fifo
from random import shuffle
from serial.tools import list_ports
import sys
import os

__version__ = "1.1.20"

COMMON_ERRORS = {
	0:'Unknown error.',
	3:'Power error.',
	4:'Calibration error.',
	5:'Output error.',
	10:'Unrecognised command.',
	11:'Unrecognised input parameter.',
	12:'Unrecognised channel, {ch}.',
	13:'Operation forbidden.',
	14:'Serial buffer overflow.',
	15:'Serial communication error.',
	16:'Command timed out.',
	17:'SPI error.',
	18:'ADC error.',
	19:'I2C error.',
	30:'Too many errors, some have been suppressed.',
	31:'Firmware trap.',
	90:'Powered up.'}

Qx_ERRORS = {
	1:'Over-voltage error on channel {ch}.',
	2:'Over-current error on channel {ch}.'}

Mx_ERRORS = {0:'Unknown error.',
	1:'Out-of-range error on channel {ch}.',
	20:'Interlock triggered on channel {ch}.'}

CMD_CODES = {'V':0x00, 'I':0x01, 'VMAX':0x02, 'IMAX':0x03, 'VCAL':0x04, 'ICAL':0x05, 'VERR':0x06, 'IERR':0x07, 'VIP':0x0A, 'SR':0x0B, 'PDI':0x0C, 'PDP':0x0D, 'PDR':0x0E, 'GAIN':0x0F, 'VFULL':0x20, 'IFULL':0x21, 'NCHAN':0x22, 'FIRMWARE':0x23, 'ID':0x24, 'LIFETIME':0x25, 'NVM':0x26, 'LOG':0x27, 'QUIET':0x28, 'LED':0x31, 'NUP':0x32, 'ADCT':0x33, 'ADCN':0x34, 'CCFN':0x35, 'INTEST':0x36, 'OK':0x37, 'DIGSUP':0x38, 'HELP':0x41, 'SAFE':0x42, 'ROCOM':0x43, 'Q': 0x44, 'EQ': 0x45, 'M': 0x48,
             'QN': 0x49, 'QL': 0x4A, 'PW': 0x4B, 'TIMER': 0x4C}

DEVICE_PROPERTIES = {
		'Q8iv':{'VFULL':12.0,'IFULL':24.0}, 
		'Q8a':{'VFULL':12.0,'IFULL':100.0}, 
		'Q8b':{'VFULL':12.0,'IFULL':83.333333}, 
		'Q8bi':{'VFULL':12.0,'IFULL':100},
		'M2':{'VFULL':8458.0,'IFULL':1375.0,'XFULL':8388352.0}}

	
RESPONSE_OK = 'OK\n'
ERROR_FORMAT = '[A-Za-z]{1,3}(\d+):(\d+)'


class Qontroller(object):
	"""
	Superclass which handles communication, enumeration, and logging.
	
	 device_id = None                    Device ID
	 serial_port = None                  Serial port object
	 serial_port_name = None             Name of port, (eg 'COM1', '/dev/tty1')
	 error_desc_dict = Q8x_ERRORS        Error code descriptions
	 log = fifo(maxlen = 256)            Log FIFO of communications
	 log_handler = None                  Function which catches log dictionaries
	 log_to_stdout = True                Copy new log entries to stdout
	 response_timeout = 0.100            Timeout for response to commands
	 inter_response_timeout = 0.050      Timeout for response to get commands
	
	Log handler:
	 The log handler may be used to catch and dynamically handle certain errors, 
	 as they arise. It is a function with a single dict argument. The dict contains
	 details of the log entry, with keys 'timestamp', 'proctime', 'type', 'id', 'ch', 
	 'value', 'desc', 'raw'. In the following example, the handler is set to raise a
	  RuntimeError upon reception of errors E01, E02, and E03:
	
	 q = Qontroller()
	
	 fatal_errors = [1, 2, 3]
	
	 def my_log_handler(err_dict):
	 	if err_dict['type'] is 'err' and err_dict['id'] in fatal_errors:
	 		raise RuntimeError('Caught Qontrol error "{1}" at {0}
	 			ms'.format(1000*err_dict['proctime'], err_dict['desc']))

	 q.log_handler = my_log_handler
	 
	 or more simply
	 
	 q.log_handler = generic_log_handler(fatal_errors)
	"""

	error_desc_dict = COMMON_ERRORS

	def __init__(self, *args, **kwargs):
		"""
		Initialiser.
		"""
		
		# Defaults
		
		self.device_id = None				# Device ID (i.e. [device type]-[device number])
		self.serial_port = None				# Serial port object
		self.serial_port_name = None		# Name of serial port, eg 'COM1' or '/dev/tty1'
		self.baudrate = 115200				# Serial port baud rate (signalling frequency, Hz)
		self.log = fifo(maxlen = 4096)		# Log FIFO of sent commands and received errors
		self.log_handler = None				# Function which catches log dictionaries
	
		self.log_to_stdout = False			# Copy new log entries to stdout
		self.response_timeout = 0.100		# Timeout for RESPONSE_OK or error to set commands
		self.inter_response_timeout = 0.050	# Timeout between received messages
		self.wait_for_responses = True		# Should we wait for responses to set commands
		
		# Set a time benchmark
		self.init_time = time.time()
		
		# Get arguments from init
		
		# Populate parameters, if provided
		for para in ['device_id', 'serial_port_name', 'log_handler', 'log_to_stdout', 'response_timeout', 'inter_response_timeout', 'baudrate', 'wait_for_responses']:
			try:
				self.__setattr__(para, kwargs[para])
			except KeyError:
				continue
		
		# Find serial port by asking it for its device id
		if 'device_id' in kwargs:
			# Search for port with matching device ID
			ob = re.match('([QS]\w+)-([0-9a-fA-F\*]+)', self.device_id)
			targ_dev_type,targ_dev_num = ob.groups()
			if ob is None:
				raise AttributeException('Entered device ID ({0}) must be of form "[device type]-[device number]" where [device number] can be hexadecimal'.format(self.device_id))
			
			# Find serial port based on provided device ID (randomise their order)
			candidates = []
			possible_ports = list(list_ports.comports())
			shuffle(possible_ports)
			tries = 0
			for port in possible_ports:
				for i in range(60):
					sys.stdout.write(' ')
				sys.stdout.write('\r')
				sys.stdout.write('Querying port {:}... '.format(port.device))
				sys.stdout.flush()
				
				try:
					# Instantiate the serial port
					self.serial_port = serial.Serial(port.device, self.baudrate, timeout=0.5)
					self.serial_port.close()
					self.serial_port.open()
					# Clear buffer
					self.serial_port.reset_input_buffer()
					self.serial_port.reset_output_buffer()
					# Transmit our challenge string
					self.serial_port.write("id?\n".encode('ascii'))
					# Receive response
					response = self.serial_port.read(size=64).decode("ascii") 
					# Check if we received a response
					if response == '':
						sys.stdout.write('No response\n')
						continue
					# Match the device ID
					ob = re.match('.*((?:'+ERROR_FORMAT+')|(?:Q\w+-[0-9a-fA-F\*]+)).*', response)
					if ob is not None:
						ob = re.match('(Q\w+)-([0-9a-fA-F\*]+)\n', response)
						if ob is not None:
							sys.stdout.write('{:}\n'.format(response))
							sys.stdout.flush()
							dev_type,dev_num = ob.groups()
							candidates.append({'dev_type':dev_type, 'dev_num':dev_num, 'port':port.device})
							if dev_type == targ_dev_type and dev_num == targ_dev_num:
								self.serial_port_name = port.device
								break
						else:
							ob = re.match(ERROR_FORMAT, response)
							if ob is not None:
								sys.stdout.write('Error')
								# Try this port again later
								if tries < 3:
									sys.stdout.write('. Will try again...')
									possible_ports.append(port)
									tries += 1
								else:
									sys.stdout.write('\n')
								sys.stdout.flush()
					else:
						sys.stdout.write('Not a valid device\n'.format(response))
						sys.stdout.flush()
							
					
					# Close port
					self.serial_port.close()
					
				except serial.serialutil.SerialException:
					sys.stdout.write('Busy\n')
					sys.stdout.flush()
					continue
			
			# If the target device is not found
			if not self.serial_port.is_open:
				# Check whether we found another possibility
				for candidate in candidates:
					if candidate['dev_type'] == targ_dev_type:
						self.device_id = candidate['dev_type']+'-'+candidate['dev_num']
						self.serial_port_name = candidate['port']
						print ('Qontroller.__init__: Warning: Specified device ID ({0}) could not be found. Using device with matching type ({2}) on port {1}.'.format(kwargs['device_id'], self.serial_port_name, self.device_id))
						break
				# If no similar device exists, abort
				if all([candidate['dev_type'] != targ_dev_type for candidate in candidates]):
					raise AttributeError('Specified device ID ({0}) could not be found.'.format(kwargs['device_id']))
			
			print ('Using serial port {0}'.format(self.serial_port_name))
			# If serial_port_name was also specified, check that it matches the one we found.
			if ('serial_port_name' in kwargs) and (self.serial_port_name != kwargs['serial_port_name']):
				print ('Qontroller.__init__: Warning: Specified serial port ({0}) does not match the one found based on the specified device ID ({1}, {2}). Using serial port {2}.'.format(kwargs['serial_port_name'], self.device_id, self.serial_port_name))
		
		# Open serial port directly, get device id
		elif 'serial_port_name' in kwargs:
			# Open serial communication
			# This will throw a serial.serialutil.SerialException if busy
			self.serial_port = serial.Serial(self.serial_port_name, self.baudrate, timeout = self.response_timeout)
			
			# Clear the input buffer (reset_input_buffer doesn't clear fully)
			self.serial_port.read(1000000)
			
			# Get device ID
			# Transmit our challenge string
			# This repeated try mechanism accounts for serial ports with starting hiccups
			timed_out = True
			for t in range(3):
				# Clear buffer
				self.serial_port.reset_input_buffer()
				self.serial_port.reset_output_buffer()
				# Send challenge
				self.serial_port.write('id?\n'.encode('ascii'))
				# Receive response
				start_time = time.time()
				# Wait for first byte to arrive
				while (self.serial_port.in_waiting == 0) and (time.time() - start_time < 0.2):
					pass
				# Read response, ignoring unparsable characters
				try:
					response = self.serial_port.read(size=64).decode('ascii')
				except UnicodeDecodeError:
					response = ""
				# Parse it
				ob = re.match('.*((?:'+ERROR_FORMAT+')|(?:\w+\d\w*-[0-9a-fA-F\*]+)).*', response)
				# Check whether it's valid
				if ob is not None:
					# Flag that we have broken out correctly
					timed_out = False
					break
			
			# Store the parsed value
			if not timed_out:
				self.device_id = ob.groups()[0]
				# Check if it was an error, in which case clear the stored value but proceed
				ob = re.match('((?:'+ERROR_FORMAT+')|(?:Q\w+-\*+))', self.device_id)
				if ob is not None:
					# It was an error (no ID assigned yet)
					self.device_id = None
			else:
				raise RuntimeError('Qontroller.__init__: Error: Unable to communicate with device on port {0} (received response {1}, "{2}").'.format(self.serial_port_name, ":".join("{:02x}".format(ord(c)) for c in response), response.replace('\n', '\\n')))
		else:
			raise AttributeError('At least one of serial_port_name or device_id must be specified on Qontroller initialisation. Available serial ports are:\n  serial_port_name = {:}'.format('\n  serial_port_name = '.join([port.device for port in list(list_ports.comports())])))
		
		
		# Establish contents of daisy chain
		try:
			# Force a reset of the daisy chain
			self.issue_command('nup', operator = '=', value = 0)
			
			# Ask for number of upstream devices, parse it
			try:
				chain = self.issue_command('nupall', operator = '?', target_errors = [0,10,11,12,13,14,15,16], output_regex = '(?:([^:\s]+)\s*:\s*(\d+)\n*)*')
			except:
				chain = self.issue_command('nup', operator = '?', target_errors = [0,10,11,12,13,14,15,16], output_regex = '(?:([^:\s]+)\s*:\s*(\d+)\n*)*')
			# Further parse each found device into a dictionary
			for i in range(len(chain)):
				ob = re.match('\x00*([^-\x00]+)-([0-9a-fA-F\*]+)', chain[i][0])
			
				device_id = chain[i][0]
				device_type = ob.groups()[0]
				device_serial = ob.groups()[1]
			
				try:
					index = int(chain[i][1])
				except ValueError:
					index = -1
					print ('Qontroller.__init__: Warning: Unable to determine daisy chain index of device with ID {:}.'.format(device_id))
			
				# Scan out number of channels from device type
				ob = re.match('[^\d]+(\d*)[^\d]*', device_type)
			
			
				try:
					n_chs = int(ob.groups()[0])
				except ValueError:
					n_chs = -1
					print ('Qontroller.__init__: Warning: Unable to determine number of channels of device at daisy chain index {:}.'.format(index))
			
				chain[i] = {
					'device_id':device_id,
					'device_type':device_type,
					'device_serial':device_serial,
					'n_chs':n_chs,
					'index':index}
		except:
			chain = []
			print ('Qontroller.__init__: Warning: Unable to determine daisy chain configuration.')
		
		self.chain = chain
	
	
	def __del__(self):
		"""
		Destructor.
		"""
		self.close()
	
	
	def close(self):
		"""
		Release resources
		"""
		if self.serial_port is not None and self.serial_port.is_open:
			# Close serial port
			self.serial_port.close()
	
	
	def transmit (self, command_string, binary_mode = False):
		"""
		Low-level transmit data method.
		
		 command_string -- str or bytearray
		"""
		# Ensure serial port is open
		if not self.serial_port.is_open:
			self.serial_port.open()
			print ("Opening serial port!")
		
		# Write to port
		if binary_mode:
			self.serial_port.write(command_string)
			self.log_append(type='tx', id='', ch='', desc=repr(command_string), raw=command_string)
		else:
			self.serial_port.write(command_string.encode('ascii'))
			self.log_append(type='tx', id='', ch='', desc=command_string, raw='')
			
		
		# Log it
		
		# This may speed things up; YMMV:
		# self.serial_port.flush()
	
	
	def receive (self):
		"""
		Low-level receive data method which also checks for errors.
		"""
		# Ensure serial port is open
		if not self.serial_port.is_open:
			self.serial_port.open()
		
		# Read from port
		lines = []
		errs = []
		
		# Check if there's anything in the input buffer
		while self.serial_port.in_waiting > 0:
			# Get a line from the receive buffer
			rcv = self.serial_port.readline()
			try:
				line = str(rcv.decode('ascii'))
			except UnicodeDecodeError as e:
				raise RuntimeError("unexpected characters in Qontroller return value. Received line '{:}'.".format(rcv) )
			
			# Check if it's an error by parsing it
			err = self.parse_error(line)
			if err is None:
				# No error, keep the line
				lines.append(line)
			else:
				# Line represents an error, add to list
				errs.append(err)
		
		# Log the lines we received
		if len(lines):
			self.log_append(type='rcv', id='', ch='', desc=lines, raw='')
		
		# Add any errors we found to our log
		for err in errs:
			self.log_append(type='err', id=err['id'], ch=err['ch'], desc=err['desc'], raw=err['raw'])
		
		return (lines, errs)
	
	
	def log_append (self, type='err', id='', ch=0, value=0, desc='', raw=''):
		"""
		Log an event; add both a calendar- and process-timestamp.
		"""
		# Append to log fifo
		self.log.append({'timestamp':time.asctime(), 'proctime':round(time.time()-self.init_time,3), 'type':type, 'id':id, 'ch':ch, 'value':value, 'desc':desc, 'raw':raw})
		# Send to handler function (if defined)
		if self.log_handler is not None:
			self.log_handler(self.log[-1])
		# Send to stdout (if requested)
		if self.log_to_stdout:
			self.print_log (n = 1)
	
	
	def print_log (self, n = None):
		"""
		Print the n last log entries. If n == None, print all log entries.
		"""
		if n is None:
			n = len(self.log)
		
		for i in range(-n,0):
			print('@ {0: 8.1f} ms, {1} : {2}'.format(1000*self.log[i]['proctime'], self.log[i]['type'], self.log[i]['desc']) )
	
	
	def parse_error (self, error_str):
		"""
		Parse an error into its code, channel, and human-readable description.
		"""
		# Strip whitespace
		error_str = error_str.strip()
		
		# Regex out the error and channel indices from the string
		ob = re.match(ERROR_FORMAT, error_str)
		
		# If error_str doesn't match an error, return None
		if ob is None:
			return None
		
		# Extract the two matched groups (i.e. the error and channel indices)
		errno,chno = ob.groups()
		errno = int(errno)
		chno = int(chno)
		
		# Get the error description; if none is defined, mark as unrecognised
		errdesc = self.error_desc_dict.get(errno, 'Unrecognised error code.').format(ch=chno)
		
		return {'type':'err', 'id':errno, 'ch':chno, 'desc':errdesc, 'raw':error_str}
	
	
	def wait (self, seconds=0.0):
		"""
		Do nothing while watching for errors on the serial bus.
		"""
		start_time = time.time()
		while time.time() < start_time + seconds:
			self.receive()
	
	
	def issue_command (self, command_id, ch=None, operator='', 
		value=None, n_lines_requested=2**31, target_errors=None, 
		output_regex='(.*)', special_timeout=None):
		"""
		Transmit command to device, get response.
		
		Command format is [command_id][ch][operator][value].
		
		 command_id          Command header
		 ch                  Channel index to apply command to
		 operator            Type of command in {?, =}
		 value               Value of set command
		 n_lines_requested   Lines of data (not error) to wait for, or timeout
		 target_errors       Error numbers which will be raised as RuntimeError
		 special_timeout     Timeout to use for this command only
		"""
		# Check for previous errors
		lines,errs = self.receive()
		
		# Transmit command
		
		if ch is None:
			ch = ''
		if value is None:
			value = ''
		if isinstance(value,list):
			tx_str = '{0}{1}{2}{3}'.format(command_id, ch, operator,value[0])
			for v in value[1:]:
				tx_str += ',{:}'.format(v)
		else:
			tx_str = '{0}{1}{2}{3}'.format(command_id, ch, operator, value)
		
		self.transmit(tx_str+'\n')
		
		# Log it
		self.log_append(type= 'set' if operator == '=' else 'get', value=value, id=command_id, ch=ch, desc='Command: "'+tx_str+'".')
		
		
		# Function to retry this command (in case of comms error)
		def retry_function():
			return self.issue_command (command_id, ch, operator, value, n_lines_requested, target_errors, output_regex)
		
		# Wait for response
		if operator=='?' or ((operator=='=' or operator=='') and self.wait_for_responses):
			result = self._issue_command_receive_response (retry_function, n_lines_requested, target_errors, output_regex, special_timeout)
			return result
		
	
	def issue_binary_command (self, command_id, ch=None, BCAST=0, ALLCH=0, ADDM=0, RW=0, ACT=0, DEXT=0, value_int=0, addr_id_num=0x0000, n_lines_requested=2**31, target_errors=None, output_regex='(.*)', special_timeout = None):
		"""
		Transmit command to device, get response.
		
		 command_id:   Command ID, either int (command index) or str (command name)
		 ch:           Channel address (max 0xFFFF for ADDM=0, 0xFF for ADDM=1)
		 BCAST,
		 ALLCH,
		 ADDM,
		 RW,
		 ACT,
		 DEXT: 		   Header bits. See Programming Manual for full description
		 value_int:    Data, either int (DEXT=0) or list of int (DEXT=1)
		 addr_id_num   Device ID code (ADDM=1 only)
		
		Other arguments are as described for issue_command().
		"""
		
		
		def get_val(i):
			"""Function to convert uint16 to bytearray([uint8,uint8])"""
			return bytearray([int(i/256),int(i)-int(i/256)*256])
		
		def parity_odd(x):
			"""Function to compute whether a byte's parity is odd."""
			x = x ^ (x >> 4)
			x = x ^ (x >> 2)
			x = x ^ (x >> 1)
			return x & 1
		
		
		# Format header byte
		header_byte  =       0x80
		header_byte += BCAST*0x40
		header_byte += ALLCH*0x20
		header_byte +=  ADDM*0x10
		header_byte +=    RW*0x08
		header_byte +=   ACT*0x04
		header_byte +=  DEXT*0x02
		header_byte += parity_odd(header_byte)
		
		
		# Format command byte
		if isinstance(command_id, str):
			command_byte = CMD_CODES[command_id.upper()]
		elif isinstance(command_id, int):
			command_byte = command_id
		
		
		# Format channel address
		address_bytes = bytearray()
		if ch is None:
			ch = 0
		if ADDM == 1:
			address_bytes.extend(get_val(addr_id_num))
			address_bytes.append(ch)
		elif ADDM == 0:
			address_bytes.append(0)
			address_bytes.extend(get_val(ch))
		
		
		# Format value bytes
		# value_int can be either an int or a list of ints (for vectorised input, DEXT = 1)
		data_bytes = bytearray()
		
		if DEXT == 1:
			# Handle data extension length
			if isinstance(value_int, list):
				n_dext_words = len(value_int)
			else:
				n_dext_words = 1
			if n_dext_words > 0xFFFF:
				n_dext_words = 0xFFFF
			data_bytes.extend(get_val(n_dext_words))
		
		if isinstance(value_int, int):
			data_bytes.extend(get_val(value_int))
		
		elif isinstance(value_int, list) and all([isinstance(e ,int) for e in value_int]):
			for i,e in enumerate(value_int):
				data_bytes.extend(get_val(e))
				if i == n_dext_words:
					break
		
		else:
			raise AttributeError("value_int must be of type int, or of type list with all elements of type int (received type {:})".format(type(value_int) ) )
		
		
		# Compose command byte string
		tx_str = bytearray()
		tx_str.append(header_byte)				# Header byte
		tx_str.append(command_byte)				# Command byte
		tx_str.extend(address_bytes)			# Three bytes of channel address
		tx_str.extend(data_bytes)				# 2 (DEXT=0) or 2*N+1 (DEXT=1) bytes of data
		
		# Transmit it
		self.transmit(tx_str, binary_mode = True)
		
		
		# Function to retry this command (in case of comms error)
		def retry_function():
			return self.issue_binary_command (command_id, ch, BCAST, ALLCH, ADDM, RW, ACT, DEXT, value_int, addr_id_num, n_lines_requested, target_errors, output_regex, special_timeout)
		
		# Wait for response
		if RW==1 or ((RW==0 or ACT) and self.wait_for_responses):
			try:
				result = self._issue_command_receive_response (retry_function, n_lines_requested, target_errors, output_regex, special_timeout)
				return result
			except RuntimeError as e:
				if RW == 1:
					# If we want a return value, raise an error
					raise RuntimeError ("Failed to read with command '{0}'. {1}".format(tx_str, e))
				else:
					# If we are setting something, just warn the user
					print("Qontroller.issue_command: Warning: Failed to write with command '{0}'. {1}".format(tx_str, e))
					return None
				
	
	
	
	def _issue_command_receive_response (self, retry_function, n_lines_requested=2**31, target_errors=None, output_regex='(.*)', special_timeout = None):
		"""
		Internal method to handle waiting for response.
		"""
		
		# Receive response
		lines = []
		errs = []
		if target_errors is None:
			target_errors = []
		start_time = time.time()
		last_message_time = start_time
		
		timeout = special_timeout if special_timeout != None else self.response_timeout
		
		
		while (True):
				
				# Break conditions
				if (RESPONSE_OK in lines):
					break
				elif (len(lines) >= n_lines_requested):
					break
				elif not all([err['id'] not in target_errors for err in errs]):
					break
				elif (time.time() - start_time > timeout):
					if (time.time() - last_message_time > self.inter_response_timeout):
						break
				
				# Receive data
				rec_lines,rec_errs = self.receive()
				
				# Update the last time a message was received
				# We won't proceed now until self.inter_response_timeout has elapsed
				if len(rec_lines) + len(rec_errs) > 0:
					last_message_time = time.time()
					
				# Integrate received lines and errors
				lines.extend(rec_lines)
				errs.extend(rec_errs)
				
				# Check whether we have received a serial comms error (E15)
				if any([err['id'] == 15 for err in errs]):
					# If we did, we should try issuing the command again, recursively
					return retry_function()
				
				# Check whether we have received a fatal error
				if any([err['id'] in target_errors for err in errs]):
					raise RuntimeError('Received target error code {0}, "{1}". Last 5 log items were: \n{2}.'.format(errs[-1]['id'], errs[-1]['desc'], '\n'.join([str(self.log[l]) for l in range(-6,-1)])))
		
		# We timed out.
		if len(lines) == 0 and len(errs) == 0:
			# If we are looking for a return value, raise an error
			raise RuntimeError ('Timed out waiting for response to command.')
		
		# Parse the output
		values = []
		for line in lines:
			op = re.match(output_regex, line)
			if op is None:
				value = (None,)
			else:
				value = op.groups()
			values.append(value)
		
		return values
	
	def __getattr__(self, attr):
		"""
		Allow convenience attribute access for certain parameters
		"""
		if (attr in ['firmware', 'vfull', 'ifull', 'lifetime']):
			return self.issue_command (command_id=attr, ch=None, operator='?', n_lines_requested=1)[0][0]


def generic_log_handler(fatal_errors='all'):
	"""
	A generic log handler which can be passed to Qontroller instances to
	generate a RuntimeError every time an error in the list fatal_errors
	is reported by the hardware.
	
	 fatal_errors    List of errors that should be raised.
	                 'all' will raise every error encountered (default).
	"""
	
	if fatal_errors == 'all':
		def _generic_log_handler(err_dict):
			if err_dict['type'] == 'err':
				raise RuntimeError('Caught Qontrol error {:} "{:}" at {:} ms'.format(err_dict['raw'], err_dict['desc'], 1000*err_dict['proctime']))
	else:
		def _generic_log_handler(err_dict):
			if err_dict['type'] == 'err' and err_dict['id'] in fatal_errors:
				raise RuntimeError('Caught Qontrol error {:} "{:}" at {:} ms'.format(err_dict['raw'], err_dict['desc'], 1000*err_dict['proctime']))
	
	return _generic_log_handler


class _ChannelVector(object):
	"""
	List class with fixed length but mutable (typed) elements, with hooks.
	"""
	
	def __init__(self, base_list, valid_types=(int,float), set_handle=None, get_handle=None):
		self.list = base_list
		self.n_ch = len(self.list)
		self.valid_types = valid_types
		try:
			len(self.valid_types)
		except:
			raise AttributeError("valid_types must be iterable.")
		self.set_handle = set_handle
		self.get_handle = get_handle

	
	def __len__(self):
		return len(self.list)
		
	
	def __getitem__(self, key):
		if isinstance(key, slice):
			# Handle slice key
			return [self[k] for k in range(len(self))[key.start:key.stop:key.step]]
		else:
			# Handle normal key
			if self.get_handle is not None:
				get_val = self.get_handle (key, self.list[key])
				if get_val is not None:
					self.list[key] = get_val
			return self.list[key]
		
	
	def __setitem__(self, key, value):
		if not isinstance(value,list):
			# Check type (list element types are handled by this recursively)
			if all([type(value) != valid_type for valid_type in self.valid_types]):
				raise TypeError('Attempt to set value to type {0} is forbidden. Valid types are {1}.'.format(type(value), self.valid_types))
		if isinstance(key, slice):
			# Handle slice key
			ks = range(len(self))[key.start:key.stop:key.step]
			if isinstance(value,list):
				if len(ks) != len(value):
					raise AttributeError('Attempt to set {0} channels of output to list of length {1}. Lengths must match.'.format(len(ks), len(values)))
				vs = value
			else:
				vs = [value] * len(ks)
			
			for i,k in enumerate(ks):
				self[k] = vs[i]
		else:
			# set_handle doesn't recognise -1 as the last element
			# so we need to update the key
			key = self.n_ch - 1 if key == -1 else key

			# Handle normal key
			if self.set_handle is not None:
				self.set_handle (key, value)
			self.list[key] = value
		
	
	def __iter__(self):
		return iter(self.list)
	
	
	def __repr__(self):
		return repr([self[i] for i in range(len(self))])



class QXOutput(Qontroller):
	"""
	Output module class. Provides channel vectors for voltage (v), current (i), 
	maximum voltage (vmax), and maximum current (imax).
	
	Compatible modules:
	- Q8iv
	- Q8a
	- Q8b
	"""
	
	error_desc_dict = {**COMMON_ERRORS, **Qx_ERRORS}

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		
		self.n_chs = 0
		self.v_full = 0
		self.i_full = 0
		self.v = None				# Channel voltages (direct access)
		self.i = None				# Channel currents (direct access)
		self.vmax = None			# Channel voltages (direct access)
		self.imax = None			# Channel currents (direct access)
		self.binary_mode = False	# Communicate in binary
		
		
		# Populate parameters, if provided
		for para in ['binary_mode']:
			try:
				self.__setattr__(para, kwargs[para])
			except KeyError:
				continue
		
		
		# Get our full-scale voltage and current (VFULL, IFULL)
		try:
			self.v_full = float(self.issue_command('vfull', operator = '?', n_lines_requested = 1, output_regex='(?:\+|-|)([\d\.]+) V')[0][0])
		except Exception as e:
			raise RuntimeError("Unable to obtain VFULL from qontroller on port {:}. Error was {:}.".format(self.serial_port_name, e))
		try:
			self.i_full = float(self.issue_command('ifull', operator = '?', n_lines_requested = 1, output_regex='(?:\+|-|)([\d\.]+) mA')[0][0])
		except:
			raise RuntimeError("Unable to obtain IFULL from qontroller on port {:}.".format(self.serial_port_name))
		
		# Get our number of channels
		try:
			# See if its in the list of kwargs
			self.n_chs = kwargs['n_chs']
			if self.n_chs <= 0 or self.n_chs == None:
				raise KeyError()
		except KeyError:
			# If not in kwargs, try to get it from the chain
			try:
				self.n_chs = sum([device['n_chs'] for device in self.chain])
			except KeyError:
				# If not, just ask the top device how many ports its got
				try:
					self.n_chs = int(self.issue_command('nchan', operator = '?', n_lines_requested = 1, target_errors = [10], output_regex = '(\d+)\n')[0][0])
				except:
					# If not, just take some random value
					self.n_chs = 8
					print ("QXOutput.__init__: Warning: Failed to obtain number of daisy-chained channels automatically. Include this as n_chs argument on initialisation to workaround.")
		
		# Generate lists of VFULL and IFULL values, for binary command scaling
		self.v_fulls = []
		self.i_fulls = []
		for d in self.chain:
			for ch in range(d['n_chs']):
				self.v_fulls.append(DEVICE_PROPERTIES[d['device_type']]['VFULL'])
				self.i_fulls.append(DEVICE_PROPERTIES[d['device_type']]['IFULL'])
		
		# Set up output direct access
		# These initialise themselves when they are first used (i.e. the 0 init is OK)
		
		# Voltage
		self.v = _ChannelVector([0] * self.n_chs)
		self.v.set_handle = lambda ch,val: self.set_value(ch,'V',val)
		self.v.get_handle = lambda ch,val: self.get_value(ch,'V')
		
		self.vmax = _ChannelVector([0] * self.n_chs)
		self.vmax.set_handle = lambda ch,val: self.set_value(ch,'VMAX',val)
		self.vmax.get_handle = lambda ch,val: self.get_value(ch,'VMAX')
		
		# Current
		self.i = _ChannelVector([0] * self.n_chs)
		self.i.set_handle = lambda ch,val: self.set_value(ch,'I',val)
		self.i.get_handle = lambda ch,val: self.get_value(ch,'I')
		
		self.imax = _ChannelVector([0] * self.n_chs)
		self.imax.set_handle = lambda ch,val: self.set_value(ch,'IMAX',val)
		self.imax.get_handle = lambda ch,val: self.get_value(ch,'IMAX')
		
		self.initialised = True
	
	
	def set_value (self, ch, para='V', new=0):
		if self.binary_mode:
			if para in ['V','VMAX']:
				full = self.v_fulls[ch]
			elif para in ['I','IMAX']:
				full = self.i_fulls[ch]
			self.issue_binary_command(CMD_CODES[para.upper()], ch=ch, RW=0, value_int=int((new/full)*0xFFFF) )
		else:
			self.issue_command(para, ch=ch, operator='=', value=new)
	
	def get_value (self, ch, para='V'):
	
		regex = '((?:\+|-){0,1}[\d\.]+)'
		if self.binary_mode:
			result = self.issue_binary_command(CMD_CODES[para.upper()], ch=ch, RW=1, n_lines_requested = 1, output_regex = regex)
		else:
			result = self.issue_command(para, ch = ch, operator = '?', n_lines_requested = 1, output_regex = regex)
		
		if len(result) > 0:
			if len(result[0]) > 0:
				s = result[0][0]
				if '.' in s:
					return float(s)
				else:
					try:
						return int(s)
					except:
						return s
		return None
	
	def get_all_values (self, para='V'):
		if self.binary_mode:
			result = self.issue_binary_command(CMD_CODES[para.upper()], RW=1, ALLCH=1, BCAST=0, n_lines_requested = self.n_chs, output_regex = '(?:\+|-|)([\d\.]+)', special_timeout = 2*self.response_timeout)
		else:
			result = self.issue_command(para+'all', operator = '?', n_lines_requested = self.n_chs, output_regex = '(?:\+|-|)([\d\.]+)', special_timeout = 2*self.response_timeout)
		if len(result) > 0:
			if len(result[0]) > 0:
				out = [None]*len(result)
				for i in range(len(result)):
					try:
						out[i] = float(result[i][0])
					except IndexError as e:
						print ("Warning: get_all_values: Failed to index result (length {:}) with error {:}.".format(len(result), e))
				return out
		return None
	
	def set_all_values (self, para='V', values=0):
		"""
		Slice up set commands into vectors for each module, and transmit.
		
		 para:      Parameter to set {'V' or 'I'}
		 values:    Either float/int or list of float/int of length n_chs
		"""
		
		if isinstance(values,list):
			# Check length
			if len(values) != self.n_chs:
				raise AttributeError("Length of values list ({:}) must match total number of channels ({:}).".format(len(values), self.n_chs))
		else:
			# If input is atomic, then set each channel to that
			values = [values] * self.n_chs
		
		if self.binary_mode:
			if para in ['V','VMAX']:
				fulls = self.v_fulls
			elif para in ['I','IMAX']:
				fulls = self.i_fulls
			
			# Convert input to ints
			for i in range(self.n_chs):
				values[i] = int((values[i]/fulls[i])*0xFFFF)
			
			# Map command name to code
			cmd_code = CMD_CODES[para.upper()]
			
			# Send vectorised outputs to each module
			i = 0
			for d in self.chain:
				n = d['n_chs']
				self.issue_binary_command(cmd_code, ch=i, RW=0, DEXT=1, value_int = values[i:i+n])
				i += n
		else:
			# Send vectorised outputs to each module
			i = 0
			for d in self.chain:
				n = d['n_chs']
				self.issue_command(para+'VEC', ch=i, operator='=', value = values[i:i+n])
				i += n
		
	
	def __setattr__(self, attr, val):
		# Prevent overwrite of internal variables
		try:
			if (self.initialised is True and attr in ['v', 'i', 'vmax', 'imax', 'v_full', 'n_chs']):
				print ("QXOutput.__setattr__: Warning: Overwriting of '{:}' is forbidden.".format(attr) )
				return
		except AttributeError:
			# If we are still initialising, carry on setting variable
			pass
		
		object.__setattr__(self, attr, val)



class MXMotor(Qontroller):
	"""
	Motor controller module class. Provides channel vectors for speed (v), 
	maximum speed (vmax), maximum winding current (imax), position (x) and 
	associated minimum (xmin) and maximum (xmax), power-of-two microsteps 
	(ustep), and motor mode (mode).
	
	Compatible modules:
	- M2
	"""
	
	error_desc_dict = {**COMMON_ERRORS, **Mx_ERRORS}
	
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)

		self.n_chs = 0
		self.v_full = 0
		self.i_full = 0
		self.x_full = 0
		self.v = None				# Channel voltages (direct access)
		self.x = None				# Channel positions (direct access)
		self.vmax = None			# Channel voltages (direct access)
		self.imax = None			# Channel currents (direct access)
		self.xmin = None			# Channel minimum positions (direct access)
		self.xmax = None			# Channel maximum positions (direct access)
		self.ustep = None			# Channel microstep (direct access)
		self.mode = None			# Channel mode (direct access)
		
		# Defaults
		
		self.binary_mode = False	# Communicate in binary
		
		
		# Populate parameters, if provided
		for para in ['binary_mode']:
			try:
				self.__setattr__(para, kwargs[para])
			except KeyError:
				continue
		
		
		# Get our full-scale voltage and current (VFULL, IFULL)
		try:
			self.v_full = float(self.issue_command('vfull', operator = '?', n_lines_requested = 1, output_regex='(?:\+|-|)([\d\.]+).*')[0][0])
		except Exception as e:
			raise RuntimeError("Unable to obtain VFULL from qontroller on port {:}. Error was {:}.".format(self.serial_port_name, e))
		try:
			self.i_full = float(self.issue_command('ifull', operator = '?', n_lines_requested = 1, output_regex='(?:\+|-|)([\d\.]+) mA')[0][0])
		except:
			raise RuntimeError("Unable to obtain IFULL from qontroller on port {:}.".format(self.serial_port_name))
		try:
			self.x_full = float(self.issue_command('xfull', operator = '?', n_lines_requested = 1, output_regex='(?:\+|-|)([\d\.]+)')[0][0])
		except:
			print("MX.__init__: Warning: Unable to obtain XFULL from qontroller on port {:}.".format(self.serial_port_name))
			self.x_full = DEVICE_PROPERTIES['M2']['XFULL']
		
		# Get our number of channels
		try:
			# See if its in the list of kwargs
			self.n_chs = kwargs['n_chs']
			if self.n_chs <= 0 or self.n_chs == None:
				raise KeyError()
		except KeyError:
			# If not in kwargs, try to get it from the chain
			try:
				self.n_chs = sum([device['n_chs'] for device in self.chain])
			except KeyError:
				# If not, just ask the top device how many ports its got
				try:
					self.n_chs = int(self.issue_command('nchan', operator = '?', n_lines_requested = 1, target_errors = [10], output_regex = '(\d+)\n')[0][0])
				except:
					# If not, just take some random value
					self.n_chs = 2
					print ("MX.__init__: Warning: Failed to obtain number of daisy-chained channels automatically. Include this as n_chs argument on initialisation to workaround. This may indicate an underlying issue in (1) communications from the PC, (2) seating of the modules in the backplane, or (3) the hardware itself.")
		
		# Generate lists of *FULL values, for binary command scaling
		self.v_fulls = []
		self.i_fulls = []
		self.x_fulls = []
		for d in self.chain:
			for ch in range(d['n_chs']):
				self.v_fulls.append(DEVICE_PROPERTIES[d['device_type']]['VFULL'])
				self.i_fulls.append(DEVICE_PROPERTIES[d['device_type']]['IFULL'])
				self.x_fulls.append(DEVICE_PROPERTIES[d['device_type']]['XFULL'])
		
		# Set up output direct access
		# These initialise themselves when they are first used (i.e. the 0 init is OK)
		
		# Voltage
		self.v = _ChannelVector([0] * self.n_chs)
		self.v.set_handle = lambda ch,val: self.set_value(ch,'V',val)
		self.v.get_handle = lambda ch,val: self.get_value(ch,'V')
		
		self.vmax = _ChannelVector([0] * self.n_chs)
		self.vmax.set_handle = lambda ch,val: self.set_value(ch,'VMAX',val)
		self.vmax.get_handle = lambda ch,val: self.get_value(ch,'VMAX')
		
		# Current
		self.imax = _ChannelVector([0] * self.n_chs)
		self.imax.set_handle = lambda ch,val: self.set_value(ch,'IMAX',val)
		self.imax.get_handle = lambda ch,val: self.get_value(ch,'IMAX')
		
		# Position
		self.x = _ChannelVector([0] * self.n_chs)
		self.x.set_handle = lambda ch,val: self.set_value(ch,'X',val)
		self.x.get_handle = lambda ch,val: self.get_value(ch,'X')
		
		self.xmin = _ChannelVector([0] * self.n_chs)
		self.xmin.set_handle = lambda ch,val: self.set_value(ch,'XMIN',val)
		self.xmin.get_handle = lambda ch,val: self.get_value(ch,'XMIN')
		
		self.xmax = _ChannelVector([0] * self.n_chs)
		self.xmax.set_handle = lambda ch,val: self.set_value(ch,'XMAX',val)
		self.xmax.get_handle = lambda ch,val: self.get_value(ch,'XMAX')
		
		# Microsteps
		self.ustep = _ChannelVector([0] * self.n_chs)
		self.ustep.set_handle = lambda ch,val: self.set_value(ch,'USTEP',val)
		self.ustep.get_handle = lambda ch,val: self.get_value(ch,'USTEP')
		
		# Modes
		self.mode = _ChannelVector([0] * self.n_chs, valid_types=(int,))
		self.mode.set_handle = lambda ch,val: self.set_value(ch,'MODE',val)
		self.mode.get_handle = lambda ch,val: self.get_value(ch,'MODE')
		
		self.initialised = True
	
	def set_value (self, ch, para='X', new=0):
		"""
		Single-channel value setter.
		"""
	
		para = para.upper()
		
		if self.binary_mode:
			if para in ['V','VMAX']:
				full = self.v_fulls[ch]
			elif para in ['I','IMAX']:
				full = self.i_fulls[ch]
			elif para in ['X','XMIN','XMAX']:
				full = self.x_fulls[ch]
				# TODO: A 32-b version of issue_binary_command is not yet implemented
				raise RuntimeError("Binary mode X commands not implemented yet. Use binary_mode = False to workaround.")
			self.issue_binary_command(CMD_CODES[para.upper()], ch=ch, RW=0, value_int=int((new/full)*0xFFFF) )
		else:
			self.issue_command(para, ch=ch, operator='=', value=new)
	
	def get_value (self, ch, para='X'):
		"""
		Single-channel value getter.
		"""
	
		para = para.upper()
	
		if self.binary_mode:
			# TODO: A 32-b version of issue_binary_command is not yet implemented
			raise RuntimeError("Binary mode X commands not implemented yet. Use binary_mode = False to workaround.")
			result = self.issue_binary_command(CMD_CODES[para.upper()], ch=ch, RW=1, n_lines_requested = 1, output_regex = '((?:\+|-){0,1}[\d\.]+)')
		else:
			result = self.issue_command(para, ch = ch, operator = '?', n_lines_requested = 1, output_regex = '((?:\+|-){0,1}[\d\.]+)')
		if len(result) > 0:
			if len(result[0]) > 0:
				s = result[0][0]
				if '.' in s:
					return float(s)
				else:
					try:
						return int(s)
					except:
						return s
		return None
	
	def get_all_values (self, para='V'):
		"""
		All-channel value getter.
		"""
		
		para = para.upper()
		
		if self.binary_mode:
			result = self.issue_binary_command(CMD_CODES[para.upper()], RW=1, ALLCH=1, BCAST=0, n_lines_requested = self.n_chs, output_regex = '(?:\+|-|)([\d\.]+)', special_timeout = 2*self.response_timeout)
		else:
			result = self.issue_command(para+'all', operator = '?', n_lines_requested = self.n_chs, output_regex = '(?:\+|-|)([\d\.]+)', special_timeout = 2*self.response_timeout)
		if len(result) > 0:
			if len(result[0]) > 0:
				out = [None]*len(result)
				for i in range(len(result)):
					try:
						out[i] = float(result[i][0])
					except IndexError as e:
						print ("Warning: get_all_values: Failed to index result (length {:}) with error {:}.".format(len(result), e))
				return out
		return None
	
	def set_all_values (self, para='V', values=0):
		"""
		Slice up set commands into vectors for each module, and transmit.
		
		 para:      Parameter to set {'X','XMIN','XMAX','VMAX','IMAX','MODE'}
		 values:    Either float/int or list of float/int of length n_chs
		"""
		
		para = para.upper()
		
		if isinstance(values,list):
			# Check length
			if len(values) != self.n_chs:
				raise AttributeError("Length of values list ({:}) must match total number of channels ({:}).".format(len(values), self.n_chs))
		else:
			# If input is atomic, then set each channel to that
			values = [values] * self.n_chs
		
		if self.binary_mode:
			if para in ['V','VMAX']:
				fulls = self.v_fulls
			elif para in ['I','IMAX']:
				fulls = self.i_fulls
			elif para in ['X','XMIN','XMAX']:
				fulls = self.x_fulls
			
			if para in ['X','XMIN','XMAX','MODE']:
				# TODO: A 32-b version of issue_binary_command is not yet implemented
				raise RuntimeError("Binary mode X commands not implemented yet. Use binary_mode = False to workaround.")
			
			# Convert input to ints
			for i in range(self.n_chs):
				values[i] = int((values[i]/fulls[i])*0xFFFF)
			
			# Map command name to code
			cmd_code = CMD_CODES[para.upper()]
			
			# Send vectorised outputs to each module
			i = 0
			for d in self.chain:
				n = d['n_chs']
				self.issue_binary_command(cmd_code, ch=i, RW=0, DEXT=1, value_int = values[i:i+n])
				i += n
		else:
			# Send vectorised outputs to each module
			i = 0
			for d in self.chain:
				n = d['n_chs']
				self.issue_command(para+'VEC', ch=i, operator='=', value = values[i:i+n])
				i += n
		
	def __setattr__(self, attr, val):
		# Prevent overwrite of internal variables
		try:
			if (self.initialised is True and attr in ['v', 'vmax', 'imax', 'x', 'xmin', 'xmax', 'mode', 'v_full', 'i_full', 'x_full', 'n_chs']):
				print ("MX.__setattr__: Warning: Overwriting of '{:}' is forbidden.".format(attr) )
				return
		except AttributeError:
			# If we are still initialising, carry on setting variable
			pass
		
		object.__setattr__(self, attr, val)
	
	def wait_until_stopped(self, channels=None, timeout=float("inf"), t_poll=0.05):
		"""
		Block execution until all motors are not in motion.
		
		  channels   Wait for channels in this list to stop. None for all channels.
		  timeout    Max time before breaking.
		  t_poll     Motor state polling time, seconds. Larger numbers give less polling.
		"""
		# In case movement was just started, ensure motion can begin before we wait
		time.sleep(0.01)
		
		# If channels is not set, wait for all channels
		if channels is None:
			channels = range(self.n_chs)
		
		t_start = time.time()

		for ch in channels:
			
			while(True):
				
				try:
					v = self.v[ch]
				except RuntimeError:
					print ("MX.wait_until_stopped: Warning: Caught v-get error while waiting.")
					v = 1
				
				if ( abs(v) < 1E-3 ):
					break
				
				if ( time.time() - t_start > timeout ):
					print ("MX.wait_until_stopped: Warning: Timed out after {:} seconds waiting for channel {:} to stop.".format(timeout, ch))
					break
				
				time.sleep(t_poll)


class SXInput(Qontroller):
	"""
	Input module class. Provides channel vectors for current (i).
	
	Arguments inherited from Qontroller:
	 device_id = None                    Device ID
	 serial_port = None                  Serial port object
	 serial_port_name = None             Name of port, (eg 'COM1', '/dev/tty1')
	 error_desc_dict                     Error code descriptions
	 log = fifo(maxlen = 256)            Log FIFO of communications
	 log_handler = None                  Function which catches log dictionaries
	 log_to_stdout = True                Copy new log entries to stdout
	 response_timeout = 0.050            Timeout for response to commands
	 inter_response_timeout = 0.020      Timeout for response to get commands
	
	Compatible modules:
	- S8i
	"""
	
	error_desc_dict = {**COMMON_ERRORS, **Qx_ERRORS}

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		
		self.n_chs = 0
		self.i_full = 0
		self.i = None				# Channel currents (direct access)
		self.gain = None			# Channel gain settings (direct access)
		self.binary_mode = False	# Communicate in binary
		
		
		# Populate parameters, if provided
		for para in ['binary_mode']:
			try:
				self.__setattr__(para, kwargs[para])
			except KeyError:
				continue
		
		# Get our number of channels
		try:
			# See if its in the list of kwargs
			self.n_chs = kwargs['n_chs']
			if self.n_chs <= 0 or self.n_chs == None:
				raise KeyError()
		except KeyError:
			# If not in kwargs, try to get it from the chain
			try:
				self.n_chs = sum([device['n_chs'] for device in self.chain])
			except KeyError:
				# If not, just ask the top device how many ports its got
				try:
					self.n_chs = int(self.issue_command('nchan', operator = '?', n_lines_requested = 1, target_errors = [10], output_regex = '(\d+)\n')[0][0])
				except:
					# If not, just take some random value
					self.n_chs = 8
					print ("SXInput.__init__: Warning: Failed to obtain number of daisy-chained channels automatically. Include this as n_chs argument on initialisation to workaround.")
		
		# Set up direct access
		# These initialise themselves when they are first used (i.e. the 0 init is OK)
		
		# Current
		self.i = _ChannelVector([0] * self.n_chs)
		self.i.set_handle = lambda ch,val: self.set_value(ch,'I',val)
		self.i.get_handle = lambda ch,val: self.get_value(ch,'I')
		
		self.imax = _ChannelVector([0] * self.n_chs)
		self.imax.set_handle = lambda ch,val: self.set_value(ch,'IMAX',val)
		self.imax.get_handle = lambda ch,val: self.get_value(ch,'IMAX')
		
		self.temp = _ChannelVector([0] * self.n_chs)
		self.temp.get_handle = lambda ch,val: self.get_value(ch,'TEMP')

		self.adcn = _ChannelVector([0] * self.n_chs)
		self.adcn.get_handle = lambda ch,val: self.get_value('ADCN')

		self.adct = _ChannelVector([0] * self.n_chs)
		self.adct.get_handle = lambda ch,val: self.get_value('ADCT')

		self.gain = _ChannelVector([0] * self.n_chs)
		self.gain.set_handle = lambda ch,val: self.set_value(ch,'GAIN',val)
		self.gain.get_handle = lambda ch,val: self.get_value(ch,'GAIN')
		
		self.initialised = True
	
	
	def set_value (self, ch, para='V', new=0):
		self.issue_command(para, ch=ch, operator='=', value=new)
	
	
	def get_value (self, ch, para='I'):
		
		# Normalise parameter case
		para = para.upper()
		
		# Define regular expression to parse, based on parameter
		if para in ['I','V']:
			regex = '([\+-]?[\d\.]+)\s*([munpf]?)[VA]'
		else:
			regex = '([\+-]?[\d\.]+)'
		
		# Issue the command, wait for response
		if self.binary_mode:
			result = self.issue_binary_command(CMD_CODES[para],
							ch=ch, RW=1, n_lines_requested = 1,
							output_regex = regex)
		else:
			result = self.issue_command(para, ch = ch, operator = '?',
							n_lines_requested = 1, output_regex = regex)
		
		
		if len(result) > 0:
			if len(result[0]) > 0:
				# If there is a regex match
				
				if len(result[0]) > 1:
					# Decode SI unit scale
					scale = 10**(-1*{'':3,'m':0,'u':3,'n':6,'p':9,'f':12}[result[0][1]])
				else:
					scale = 1
				
				s = result[0][0]
				if '.' in s:
					return float(s)*scale
				else:
					try:
						return int(s)*scale
					except:
						return s
		else:
			return None
	
	
	def get_all_values (self, para='V'):
		if self.binary_mode:
			result = self.issue_binary_command(CMD_CODES[para.upper()], RW=1, ALLCH=1, BCAST=0, n_lines_requested = self.n_chs, output_regex = '(?:\+|-|)([\d\.]+)', special_timeout = 2*self.response_timeout)
		else:
			result = self.issue_command(para+'all', operator = '?', n_lines_requested = self.n_chs, output_regex = '(?:\+|-|)([\d\.]+)', special_timeout = 2*self.response_timeout)
		if len(result) > 0:
			if len(result[0]) > 0:
				out = [None]*len(result)
				for i in range(len(result)):
					try:
						out[i] = float(result[i][0])
					except IndexError as e:
						print ("Warning: get_all_values: Failed to index result (length {:}) with error {:}.".format(len(result), e))
				return out
		return None
	
	def set_all_values (self, para='V', values=0):
		"""
		Slice up set commands into vectors for each module, and transmit.
		
		 para:      Parameter to set {'V' or 'I'}
		 values:    Either float/int or list of float/int of length n_chs
		"""
		
		if isinstance(values,list):
			# Check length
			if len(values) != self.n_chs:
				raise AttributeError("Length of values list ({:}) must match total number of channels ({:}).".format(len(values), self.n_chs))
		else:
			# If input is atomic, then set each channel to that
			values = [values] * self.n_chs
		
		if self.binary_mode:
			if para in ['V','VMAX']:
				fulls = self.v_fulls
			elif para in ['I','IMAX']:
				fulls = self.i_fulls
			
			# Convert input to ints
			for i in range(self.n_chs):
				values[i] = int((values[i]/fulls[i])*0xFFFF)
			
			# Map command name to code
			cmd_code = CMD_CODES[para.upper()]
			
			# Send vectorised outputs to each module
			i = 0
			for d in self.chain:
				n = d['n_chs']
				self.issue_binary_command(cmd_code, ch=i, RW=0, DEXT=1, value_int = values[i:i+n])
				i += n
		else:
			# Send vectorised outputs to each module
			i = 0
			for d in self.chain:
				n = d['n_chs']
				self.issue_command(para+'VEC', ch=i, operator='=', value = values[i:i+n])
				i += n
		
	
	def __setattr__(self, attr, val):
		# Prevent overwrite of internal variables
		try:
			if (self.initialised is True and attr in ['v', 'i', 'vmax', 'imax', 'v_full', 'n_chs']):
				print ("QXOutput.__setattr__: Warning: Overwriting of '{:}' is forbidden.".format(attr) )
				return
		except AttributeError:
			# If we are still initialising, carry on setting variable
			pass
		
		object.__setattr__(self, attr, val)


def run_interactive_shell(serial_port_name = None):
	"""Shell for interacting directly with Qontrol hardware."""
	
	print ("- "*14)
	print (" Qontrol Interactive Shell")
	print ("- "*14+"\n")
	
	baudrate = 115200
	
	def tty_supports_color():
		"""
		Returns True if the running system's terminal supports color, and False
		otherwise. From django.core.management.color.supports_color.
		"""
		
		plat = sys.platform

		if plat == "win32":
			return False
		else:
			supported_platform = plat != 'Pocket PC' and (plat != 'win32' or
													  'ANSICON' in os.environ)
		# isatty is not always implemented, #6223.
			is_a_tty = hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()
			return supported_platform and is_a_tty
			

	if tty_supports_color():
		normal_text = "\033[0m"
		in_text = "\033[33;1m"
		out_text = "\033[36;1m"
		emph_text = "\033[97;1m"
	else:
		normal_text = ""
		in_text = ""
		out_text = ""
		emph_text = ""
	
	# List available serial ports
	#  Separate ports that are probably Qontrol devices from those that are probably not
	ports_of_interest = list(list_ports.grep('.*usbserial-FT[A-Z0-9].*'))
	ports_other = [port for port in list(list_ports.grep('.*')) 
									if port not in ports_of_interest]
	ports = ports_of_interest + ports_other
	n_ports = len(ports)
	print ("Available ports:")
	i = 0
	for port in ports_of_interest:
		print (" {:}#{:2} - {:15}{:}".format(emph_text, i, str(port), normal_text))
		i += 1
	for port in ports_other:
		print (" #{:2} - {:15}".format(i, str(port)))
		i += 1
	
	# Ask user which port to target
	if serial_port_name is None:
		for i in range(3):
			requested_port_str = input("\nWhich would you like to communicate with? #")
			try:
				requested_port_index = int(requested_port_str)
				if requested_port_index > n_ports:
					raise RuntimeError()
				break
			except:
				print ("Port index '{:}' not recognised.".format(requested_port_str))
		
		for i,port in enumerate(ports):
			if i == requested_port_index:
				break
	else:
		for port in ports:
			if port.device == serial_port_name:
				break
	
	
	port = serial.Serial(port.device, baudrate, timeout = 0)
	
	
	# Multithread the user and hardware monitoring
	import threading, copy, collections

	class WatcherThread(threading.Thread):

		def __init__(self, stream, name='keyboard-input-thread'):
			self.stream = stream
			self.buffer = fifo(maxlen = 8) # Unlikely to ever need > 1
			super(WatcherThread, self).__init__(name=name, daemon=True)
			self.stop_flag = False
			self.start()

		def run(self):
			while True:
				r = self.stream.readline()
				if r:
					if type(r) is bytes:
						try:
							self.buffer.appendleft(r.decode('ascii'))
						except UnicodeDecodeError:
							import binascii
							self.buffer.appendleft(str(binascii.hexlify(r)))
					else:
						self.buffer.appendleft(r)
				if self.stop_flag:
					break
		
		def has_data(self):
			return (len(self.buffer) > 0)
		
		def pop(self):
			return self.buffer.pop()
		
		def stop(self):
			self.stop_flag = True

	# Start threads
	user_watcher = WatcherThread(sys.stdin)
	hardware_watcher = WatcherThread(port)
	
	print ("\nEntering interactive mode. Use Ctrl+C/stop/quit/exit to finish.\n")
	print ("- "*14+'\n')
	sys.stdout.write(out_text + " > " + normal_text)
	sys.stdout.flush()
	cmd = ""
	resp = ""
	try:
		while True:
			
			# Handle commands from user
			if user_watcher.has_data():
				cmd = user_watcher.pop().strip()
				
				# Safe words
				if cmd in ['quit', 'exit', 'stop']:
					break
				
				cmd = cmd + '\n'
				port.write(cmd.encode('ascii'))
				
				
# 				sys.stdout.write("\r"+" "*40+"\r")
# 				sys.stdout.write('> ' + cmd.strip() + "\r\n")
				sys.stdout.write(out_text + " > " + normal_text)
				sys.stdout.flush()
			
			# Handle response from hardware
			if hardware_watcher.has_data():
				resp = hardware_watcher.pop()
				
				resp = resp.strip()
				sys.stdout.write("\r"+" "*40+"\r")
				sys.stdout.write(in_text + " < " + normal_text + resp + "\r\n")
				sys.stdout.write(out_text + " > " + normal_text)
				sys.stdout.flush()
	
	except KeyboardInterrupt:
		print("\n")
	
	# Kill our threaded friends
	try:
		user_watcher._stop()
	except:
		pass
	try:
		hardware_watcher._stop()
	except:
		pass
	
	print ("- "*14+'\n')
	
	print ("Interactive shell closed.")




if __name__ == '__main__':
	
	import sys, getopt
	
	run_interactive_shell()
	
	
