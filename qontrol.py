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
from collections import namedtuple
from random import shuffle
from serial.tools import list_ports
import sys
import os
import time
import random
import pdb
from enum import Enum, IntFlag, Flag
from dataclasses import dataclass, field
import struct
from functools import reduce

__version__ = "1.1.16"

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


CMD_CODES = {'V':0x00, 'I':0x01, 'VMAX':0x02, 'IMAX':0x03, 'VCAL':0x04, 'ICAL':0x05, 'VERR':0x06, 'IERR':0x07, 'VIP':0x0A, 'SR':0x0B, 'PDI':0x0C, 'PDP':0x0D, 'PDR':0x0E, 'GAIN':0x0F, 'VFULL':0x20, 'IFULL':0x21, 'NCHAN':0x22, 'FIRMWARE':0x23, 'ID':0x24, 'LIFETIME':0x25, 'NVM':0x26, 'LOG':0x27, 'QUIET':0x28, 'LED':0x31, 'NUP':0x32, 'ADCT':0x33, 'ADCN':0x34, 'CCFN':0x35, 'INTEST':0x36, 'OK':0x37, 'DIGSUP':0x38, 'HELP':0x41, 'SAFE':0x42, 'ROCOM':0x43}


DEVICE_PROPERTIES = {
                'Q8iv':{'VFULL':12.0,'IFULL':24.0}, 
                'Q8b':{'VFULL':12.0,'IFULL':83.333333}, 
                'Q8bi':{'VFULL':12.0,'IFULL':100},
                'M2':{'VFULL':8458.0,'IFULL':1375.0,'XFULL':8388352.0}}

        
RESPONSE_OK = 'OK\n'


DEV_ID_PARTS_REGEX = re.compile(r'(Q\w+)-([0-9a-fA-F]+)')
DEV_ID_REGEX = re.compile(r'\w+\d\w*-[0-9a-fA-F\*]+')


class ExtendedEnum(Enum):
    def __str__(self):
        """Returns the enum name as a str"""
        return self.name

    @classmethod
    def list(cls):
        """Returns a list of all enum strings"""
        return list(map(lambda c: str(c), cls))

    @classmethod
    def export_to(cls, namespace):
        namespace.update(cls.__members__)

    
class Header(IntFlag):
    BIN   = 0x80
    BCAST = 0x40
    ALLCH = 0x20
    ADDM  = 0x10
    RW    = 0x08
    ACT   = 0x04
    DEXT  = 0x02
 #   PBIT  = 0x01  This shouldn't be user accesible

globals().update(Header.__members__)

class Type(ExtendedEnum):
    GET = '?'
    SET = '='

Type.export_to(globals())


class HeaderMode(ExtendedEnum):
    WRITE       = BIN               # 0x81
    WRITE_DEXT  = BIN | DEXT        # 0x82
    WRITE_ALLCH = BIN | ALLCH       # 0xA0
    
    READ        = BIN | RW           # 0x88
    READ_ALLCH  = BIN | RW | ALLCH   # 0xA9

    ACT_M       = BIN | ACT          # 0x84



globals().update(HeaderMode.__members__)


class CmdIndex(ExtendedEnum):
   # command   |code  |supported header modes
    V        = (0x00, {WRITE, WRITE_DEXT, WRITE_ALLCH, READ, READ_ALLCH})
    I        = (0x01, {WRITE, WRITE_DEXT, WRITE_ALLCH, READ, READ_ALLCH})
    VMAX     = (0x02, {WRITE, WRITE_DEXT, WRITE_ALLCH, READ, READ_ALLCH})
    IMAX     = (0x03, {WRITE, WRITE_DEXT, WRITE_ALLCH, READ, READ_ALLCH})
    VCAL     = (0x04, {WRITE, ACT_M, WRITE_ALLCH, READ, READ_ALLCH})
    ICAL     = (0x05, {WRITE, ACT_M, WRITE_ALLCH, READ, READ_ALLCH})
    VERR     = (0x06, {READ, READ_ALLCH})
    IERR     = (0x07, {READ, READ_ALLCH})
    VIP      = (0x0A, {READ_ALLCH})
    SR       = (0x0B, set()) # Not in Programming Manual
    PDI      = (0x0C, set()) # Not in Programming Manual
    PDP      = (0x0D, set()) # Not in Programming Manual
    PDR      = (0x0E, set()) # Not in Programming Manual
    GAIN     = (0x0F, set()) # Not in Programming Manual
    VFULL    = (0x20, {READ_ALLCH})
    IFULL    = (0x21, {READ_ALLCH})
    NCHAN    = (0x22, {READ_ALLCH})
    FIRMWARE = (0x23, {READ, READ_ALLCH})
    ID       = (0x24, {READ, READ_ALLCH})
    LIFETIME = (0x25, {READ, READ_ALLCH})
    NVM      = (0x26, {WRITE_ALLCH, READ_ALLCH})
    LOG      = (0x27, {READ, READ_ALLCH})
    QUIET    = (0x28, set()) # Not in Programming Manual
    LED      = (0x31, {WRITE, READ, READ_ALLCH, WRITE_ALLCH})
    NUP      = (0x32, {WRITE, READ})
    ADCT     = (0x33, {WRITE, READ, READ_ALLCH, WRITE_ALLCH})
    ADCN     = (0x34, {WRITE, READ, READ_ALLCH, WRITE_ALLCH})
    CCFN     = (0x35, {WRITE, READ, READ_ALLCH, WRITE_ALLCH})
    INTEST   = (0x36, {ACT_M})
    OK       = (0x37, {WRITE, READ, READ_ALLCH, WRITE_ALLCH})
    DIGSUP   = (0x38, set()) # Not in Programming Manual
    HELP     = (0x41, {READ})
    SAFE     = (0x42, {WRITE, READ, READ_ALLCH, WRITE_ALLCH})
    ROCOM    = (0x43, {WRITE, READ, READ_ALLCH, WRITE_ALLCH})

    def code(self):
        return self.value[0]

    def header_modes(self):
        return self.value[1]

    def supports(self, *header_modes):
        return all([h in self.header_modes() for h in header_modes])
    
CmdIndex.export_to(globals())


@dataclass
class Command:
    idx: CmdIndex
    addr: int = 0
    addr_id: int = 0
    header: Header = BIN
    data: int | list[int] | float | list[float] = None
    

    def __post_init__(self):
        # Add type info to header
        self.header |= BIN

        # If there is data this is a WRITE command
        if not self.data:
            self.header |= RW
            
    def _parity_odd(self, x):
        """Function to compute whether a byte's parity is odd."""
        x = x ^ (x >> 4)
        x = x ^ (x >> 2)
        x = x ^ (x >> 1)
        return x & 1

    def type(self):
        if RW in self.header:
            return GET
        else:
            return SET

    def ascii(self):
        self.addr = 'ALL' if ALLCH in self.header else self.addr
        data = self._format_ascii_data(self.data)

        type = self.type().value
        
        return f'{self.idx}{self.addr}{type}{data}\n'

    def _format_ascii_data(self, data):
        if not self.data:
            return ''
        
        if isinstance(self.data, list):
            # Format the data into a str of the format:
            # d1, d2, d3 ...
            data_str = reduce(lambda s, x: s + f',{x}',
                              self.data[1:], str(self.data[0]))
        else:
            data_str = str(self.data)

        return data_str

    def binary(self):
        if self.data is None:
            self.data = 0

        # Compute header parity
        header = self.header
        header |= self._parity_odd(self.header)
        
        # Handle addressing modes
        # If ADDM = 1
        if ADDM in self.header:
            # addr = 2B for device id, 1BN for CH
            addr_fmt = '>Hc'
            addr = (self.addr_id, bytes([self.addr]))
        else:
            # addr = 1B padding, 2B for CH
            addr_fmt = '>xH'
            addr =(self.addr,)

        # Handle data extension
        # If DEXT = 1
        if DEXT in self.header:
            # data = 2B for # words (N), N * 2B for data words
            data_fmt = 'H' * (len(self.data) + 1)
            data = (len(self.data), *self.data)
        else:
            # data = 2B
            data_fmt = 'H'
            data = (self.data,)

        # Pack data into bytes
        h_idx_bytes = struct.pack('<cc', bytes([header]), bytes([self.idx.value[0]]))
        payload_bytes = struct.pack(addr_fmt + data_fmt, *addr, *data)

        return h_idx_bytes + payload_bytes

    def allowed(self):
        header_modes = map(lambda x: x.value, self.idx.header_modes())
        return self.header in header_modes


# Alias Command
Cmd = Command

@dataclass
class Response:
    raw_data: list[bytes] = None
    


class ErrorType(ExtendedEnum):
    UNKNOWN             = (0, 'Unknown error.')
    POWER               = (3, 'Power error.')
    CAL                 = (4, 'Calibration error.')
    OUTPUT              = (5, 'Output error.')
    UNREC_CMD           = (10, 'Unrecognised command.')
    UNREC_INPUT         = (11, 'Unrecognised input parameter.')
    UNREC_CH            = (12, 'Unrecognised channel, {ch}.')
    FORBIDDEN           = (13, 'Operation forbidden.')
    SERIAL_BUF_OVERFLOW = (14, 'Serial buffer overflow.')
    SERIAL_COMM         = (15, 'Serial communication error.')
    CMD_TIMED_OUT       = (16, 'Command timed out.')
    SPI                 = (17, 'SPI error.')
    ADC                 = (18, 'ADC error.')
    I2C                 = (19, 'I2C error.')
    TOO_MANY            = (30, 'Too many errors, some have been suppressed.')
    FIRMWARE_TRAP       = (31, 'Firmware trap.')
    POWERED_UP          = (90, 'Powered up.')

    def code(self):
        return self.value[0]

    def desc(self):
        return self.value[1]


    @classmethod
    def from_code(cls, code):
        for c in cls:
            if c.value[0] == code:
                return c

        return cls.UNKNOWN
            
@dataclass
class Error:
    type: ErrorType
    ch: int
    raw: str

    ERROR_FORMAT = r'[A-Za-z]{1,3}(\d+):(\d+)'
    
    @classmethod
    def from_str(cls, s):
        s = s.strip()
        e_match = re.match(cls.ERROR_FORMAT, s)

        if not e_match:
            return None

        errno = int(e_match.group(1))
        ch = int(e_match.group(2))

        return cls(ErrorType.from_code(errno), ch, s)

    def to_dict(self):
        return {'type': 'err', 'id': self.type.code(), 'ch': self.ch,
                'desc': self.type.desc(), 'raw': self.raw}
    
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

        def __init__(self, device_id=None, serial_port_name=None,
                     response_timeout=0.100, inter_response_timeout=0.050,
                     wait_for_responses=True, baudrate=115200,
                     log_handler=None, log_to_stdout=False,
                     virtual_port=None, log_max_len=4096):
                """
                Initialiser.
                """
                

                # Device ID (i.e. [device type]-[device number])
                self.device_id = device_id
                
                # Serial port object
                self.serial_port = None

                # Name of serial port, eg 'COM1' or '/dev/tty1'
                self.serial_port_name = serial_port_name

                # Serial port baud rate (signalling frequency, Hz)
                self.baudrate = baudrate


                self.log_max_len = log_max_len
                
                # Log FIFO of sent commands and received errors
                self.log = fifo(maxlen = log_max_len)

                # Function which catches log dictionaries
                self.log_handler = log_handler

                # Copy new log entries to stdout
                self.log_to_stdout = log_to_stdout

                # Timeout for RESPONSE_OK or error to set commands
                self.response_timeout = response_timeout

                # Timeout between received messages
                self.inter_response_timeout = inter_response_timeout

                # Should we wait for responses to set commands
                self.wait_for_responses = wait_for_responses 
                
                # Set a time benchmark
                self.init_time = time.time()

                # Virtual port
                self.virtual_port = virtual_port

                # Connect to device over serial port
                self._connect_to_device(device_id, serial_port_name)
                self._establish_daisy_chain()
        
        
        def __del__(self):
                """
                Destructor.
                """
                self.close()

        ##########################################################################################
        # Public API
        ##########################################################################################
        
        
        def close(self):
                """
                Release resources
                """
                if self.serial_port is not None and self.serial_port.is_open:
                        # Close serial port
                        self.serial_port.close()


        ##########################################################################################
        # Device Connection Functions
        ##########################################################################################

        
        def _connect_to_device(self, device_id, serial_port_name):
            # Find serial port by asking it for its device id
            if device_id:
                self._connect_via_device_id(device_id)

                # If serial_port_name was also specified,
                # check that it matches the one# we found.
                if serial_port_name and (self.serial_port_name != serial_port_name):
                    print(('Qontroller.__init__: Warning: '
                           f'Specified serial port ({kwargs["serial_port_name"]}) does not match '
                           f'the one found based on the specified device ID ({self.device_id}). '
                           f'Using serial port {self.serial_port_name}'))
                            
                            
                
            # Open serial port directly, get device id
            elif serial_port_name:
                connected, res, port = self._connect_to_serial_port(serial_port_name)

                if connected:
                    self.serial_port = port
                    self.device_id = res
                else: 
                    raise RuntimeError(('Qontroller.__init__: Error: '
                                        'Unable to communicate with '
                                        f'device on port {self.serial_port_name}'
                                        f' (received response "{res}").'))

            elif self.virtual_port:
                self.serial_port = self.virtual_port 
            else:
                avail_ports = ''.join([f'serial_port_name = {port.device}\n'
                    for port in list(list_ports.comports())])
                    
                raise AttributeError(('At least one of serial_port_name or device_id must be'
                                      ' specified on Qontroller initialisation. '
                                      f'Available serial ports are:\n{avail_ports}'))
            
        def _connect_via_device_id(self, device_id):
            connected, candidates = self._connect_to_port_for_device(device_id)

            # Found the device, nothing else to do
            if connected:
                print(f'Using serial port {self.serial_port_name}')
                return True

            # The device was not found
            # Try to see if there are any suitable candidates

            # Parse device id
            targ_dev_type, targ_dev_num = self._parse_device_id(device_id)
            
           
            found_suitable_device = False
            # If a candidate exists 
            for candidate in candidates:

                # If we have already found a suitable device
                # close the port on this candidate
                if found_suitable_device:
                    candidates['port'].close()

                # Check whether we found another possibility
                if candidate['dev_type'] == targ_dev_type:
                    # We did
                    found_suitable_device = True
                    
                    self.device_id = f"{candidate['dev_type']}-{candidate['dev_num']}"
                    self.serial_port_name = candidate['port_name']
                    self.serial_port = candidate['port']

                    print((f'Qontroller.__init__: Warning: '
                               f'Specified device ID ({device_id}) could not be found. '
                               f'Using device with matching type ({self.device_id})'
                               f' on port {self.serial_port_name}.'))

                    
            
            if not found_suitable_device:
                # If no similar device exists, abort
                raise AttributeError((f'Specified device ID ({device_id}) '
                                      'could not be found'))
            


           

        def _connect_to_port_for_device(self, device_id):

            targ_dev_type, targ_dev_num = self._parse_device_id(device_id)

            if not targ_dev_type:
                raise AttributeError((f'Entered device ID ({device_id}) must be of form'
                                      ' "[devicetype]-[device number]" where '
                                      '[device number] can be hexadecimal'))

            # Find serial port based on provided device ID (randomise their order)
            possible_ports = list(list_ports.comports())
            shuffle(possible_ports)
            
            tries = 0

            # Keep candidate devices
            candidates = []
            
            
            for port in possible_ports:
                print(f'Querying port {port.device}... ', end='')
                                
                try:
                    connected, res, serial_port_cand = self._connect_to_serial_port(port.device)

                except serial.serialutil.SerialException:
                    print('Busy')
                    continue
                    
                # Check if we received a response
                if not connected:
                    print('No response')
                    serial_port_cand.close()
                    continue
                        
                # Match the device ID
                res_match = DEV_ID_PARTS_REGEX.match(res)
                if res_match:
                    print(f'{res}')
                    dev_type, dev_num = res_match.groups()
                            
                    if dev_type == targ_dev_type and dev_num == targ_dev_num:
                        self.serial_port_name = port.device
                        self.serial_port = serial_port_cand
                        return True, candidates
                    
                    else:
                        res = res.strip('\n')
                        print((f'Found {res} but it is not'
                               f' the device we are looking for.'))
                            
                        candidates.append({'dev_type':dev_type,
                                           'dev_num':dev_num,
                                           'port_name':port.device,
                                           'port': serial_port_cand})
                        continue
                        
                # If the response wasn't an id, try to match it as an error
                if not dev_id:
                    print('Error', end='')
                        
                    # Try this port again later
                    if tries < 3:
                        print('. Will try again...', end='')
                        possible_ports.append(port)
                        tries += 1
                    else:
                        print('')

                        serial_port_cand.close()
                        continue
           
                
                # Port isn't the one we need
                serial_port_cand.close()


            return False, candidates
                            
                
                
        def _connect_to_serial_port(self, name):
            # Open serial communication
            # This will throw a serial.serialutil.SerialException if busy
            serial_port = serial.Serial(name,
                self.baudrate, timeout=self.response_timeout)
                        
                        
            # Clear the input buffer (reset_input_buffer doesn't clear fully)
            serial_port.read(1000000)
                        
            # Get device ID
            # Transmit our challenge string
            # This repeated try mechanism accounts for serial ports with starting hiccups
            timed_out = True
            timeout = 0.2 # seconds
            for t in range(3):
                
                # Clear buffer
                serial_port.reset_input_buffer()
                serial_port.reset_output_buffer()
                
                # Send challenge
                serial_port.write('id?\n'.encode('ascii'))
                
                # Receive response
                start_time = time.time()
                
                # Wait for first byte to arrive
                while (serial_port.in_waiting == 0) and (time.time() - start_time < timeout):
                    
                    # Read response, ignoring unparsable characters
                    try:
                        response = serial_port.read(size=64).decode('ascii')
                    except UnicodeDecodeError:
                        response = ""
                                # Parse it
                    ob = DEV_ID_REGEX.match(response)
                    # Check whether it's valid
                    if ob:
                        # Flag that we have broken out correctly
                        timed_out = False
                        break

            return (not timed_out), response, serial_port

    
        def _establish_daisy_chain(self):
             # Establish contents of daisy chain
             try:
                 
                # Force a reset of the daisy chain
                self.issue_command('nup', operator = '=', value = 0)
                        
                # Ask for number of upstream devices, parse it
                try:
                    chain = self.issue_command('nupall', operator = '?',
                        target_errors = [0,10,11,12,13,14,15,16],
                        output_regex = r'(?:([^:\s]+)\s*:\s*(\d+)\n*)*')
                except:
                    chain = self.issue_command('nup', operator = '?',
                        target_errors = [0,10,11,12,13,14,15,16],
                        output_regex = r'(?:([^:\s]+)\s*:\s*(\d+)\n*)*')
   
                # Further parse each found device into a dictionary
                for i in range(len(chain)):
                    ob = re.match(r'\x00*([^-\x00]+)-([0-9a-fA-F\*]+)', chain[i][0])
                        
                    device_id = chain[i][0]
                    device_type = ob.groups()[0]
                    device_serial = ob.groups()[1]
                        
                    try:
                        index = int(chain[i][1])
                    except ValueError:
                        index = -1
                        print(('Qontroller.__init__: Warning: Unable to determine'
                               f' daisy chain index of device with ID {device_id}.'))
                        
                # Scan out number of channels from device type
                ob = re.match(r'[^\d]+(\d*)[^\d]*', device_type)
                
                try:
                    n_chs = int(ob.groups()[0])
                except ValueError:
                    n_chs = -1
                    print(('Qontroller.__init__: Warning: Unable to determine'
                           f' number of channels of device at daisy chain index {index}.'))
                chain[i] = {
                    'device_id':device_id,
                    'device_type':device_type,
                    'device_serial':device_serial,
                    'n_chs':n_chs,
                    'index':index}
                
             except:
                 chain = []
                 print(('Qontroller.__init__: Warning: Unable to determine '
                        'daisy chain configuration.'))
                
             self.chain = chain

        ##########################################################################################
        # Utilities
        ##########################################################################################

        def _parse_device_id(self, device_id):    
            # Search for port with matching device ID
            device_id_match = DEV_ID_PARTS_REGEX.fullmatch(device_id)
           
            if not device_id_match:
                return None, None
            
            dev_type, dev_num = device_id_match.groups()

            return dev_type, dev_num
        
        def transmit(self, command_string, binary_mode = False):
            """
            Low-level transmit data method.

             command_string -- str or bytearray
            """
            # Ensure serial port is open
            if not self.serial_port.is_open:
                    self.serial_port.open()
                    print("Opening serial port!")

            # Write to port
            if binary_mode:
                    self.serial_port.write(command_string)
                    self.log_append(type='tx', id='', ch='',
                                    desc=command_string.hex(), raw=command_string)
            else:
                    self.serial_port.write(command_string.encode('ascii'))
                    self.log_append(type='tx', id='', ch='', desc=command_string, raw='')
                    
                        
        
        
        def receive(self):
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
                    raise RuntimeError(('Unexpected characters in Qontroller return value.'
                                       'Received line "{rcv}".'))

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
                self.log_append(type='err', id=err['id'], ch=err['ch'],
                                desc=err['desc'], raw=err['raw'])

            return (lines, errs)
        

        
        
        def log_append (self, type='err', id='', ch=0, value=0, desc='', raw=''):
            """
            Log an event; add both a calendar- and process-timestamp.
            """
            # Append to log fifo
            self.log.append({'timestamp':time.asctime(),
                             'proctime':round(time.time()-self.init_time,3),
                             'type':type, 'id':id, 'ch':ch,
                             'value':value, 'desc':desc, 'raw':raw})

            # Send to handler function (if defined)
            if self.log_handler is not None:
                self.log_handler(self.log[-1])

            # Send to stdout (if requested)
            if self.log_to_stdout:
                self.print_log (n = 1)
        
        
        def print_log (self, n=None):
            """
            Print the n last log entries. If n == None, print all log entries.
            """
            n = len(self.log) if n is None else n

            

            for i in range(-n,0):
                timestamp = round(1000*self.log[i]['proctime'], 2)
                type = self.log[i]['type']
                desc = self.log[i]['desc']
                print(f'@ {timestamp} ms, {type} : {desc}')
        
        
        def parse_error (self, error_str):
            """
            Parse an error into its code, channel, and human-readable description.
            """
            error = Error.from_str(error_str)

            if error:
                return error.to_dict()
        
        
        def wait (self, seconds=0.0):
            """
            Do nothing while watching for errors on the serial bus.
            """
            start_time = time.time()
            while time.time() < start_time + seconds:
                    self.receive()
        
        
        def issue_command(self, command_id, ch=None, operator='', 
                value=None, n_lines_requested=2**31, target_errors=None, 
                output_regex=r'(.*)', special_timeout=None, return_cmd=False):
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

                ch = '' if not ch else ch
                cmd = Command(CmdIndex[command_id.upper()], addr=ch, data=value)

                if ch == 'all':
                    cmd.header |= ALLCH

                if isinstance(value, list):
                    cmd.header |= DEXT

                if operator == '?':
                    cmd.header |= RW

            
                tx_str = cmd.ascii()

                # FIXME: Only needed for tests again current
                # programs 
                if command_id.islower():
                    tx_str = tx_str.lower()
                
                self.transmit(tx_str)
 
                # Log it
                self.log_append(type= 'set' if cmd.type() == SET else 'get', value=value,
                                id=command_id, ch=ch, desc='Command: "'+tx_str+'".')

                
                # Function to retry this command (in case of comms error)
                def retry_function():
                    return self.issue_command(command_id, ch, operator, value,
                                              n_lines_requested, target_errors, output_regex)

                
                # Wait for response
                if cmd.type() == GET or ((cmd.type() == SET) and self.wait_for_responses):
                    result = self._issue_command_receive_response(retry_function,
                        n_lines_requested, target_errors, output_regex, special_timeout)
                    
                    return result

                
                
        
        def issue_binary_command(self, command_id, ch=None, BCAST=0, ALLCH=0, ADDM=0, RW=0, ACT=0, DEXT=0, value_int=0, addr_id_num=0x0000, n_lines_requested=2**31, target_errors=None, output_regex=r'(.*)', special_timeout = None):
                """
                Transmit command to device, get response.
                
                 command_id:   Command ID, either int (command index) or str (command name)
                 ch:           Channel address (max 0xFFFF for ADDM=0, 0xFF for ADDM=1)
                 BCAST,
                 ALLCH,
                 ADDM,
                 RW,
                 ACT,
                 DEXT:             Header bits. See Programming Manual for full description
                 value_int:    Data, either int (DEXT=0) or list of int (DEXT=1)
                 addr_id_num   Device ID code (ADDM=1 only)
                
                Other arguments are as described for issue_command().
                """

                header = BIN
                header |= Header.BCAST if BCAST else BIN
                header |= Header.ALLCH if ALLCH else BIN
                header |= Header.ADDM if ADDM else BIN
                header |= Header.RW if RW else BIN
                header |= Header.ACT if ACT else BIN
                header |= Header.DEXT if DEXT else BIN
                
                cmd = Command(CmdIndex[command_id], addr=ch, addr_id=addr_id_num,
                              data=value_int, header=header)

                tx_str = cmd.binary()
                self.transmit(tx_str, binary_mode=True)
                
                # Function to retry this command (in case of comms error)
                def retry_function():
                    return self.issue_binary_command(command_id, ch, BCAST, ALLCH,
                                                     ADDM, RW, ACT, DEXT, value_int,
                                                     addr_id_num, n_lines_requested,
                                                     target_errors, output_regex,
                                                     special_timeout)
                
                # Wait for response
                if RW==1 or ((RW==0 or ACT) and self.wait_for_responses):
                    try:
                        result = self._issue_command_receive_response(retry_function,
                            n_lines_requested, target_errors,
                            output_regex, special_timeout)
                        return result
                    except RuntimeError as e:
                        if RW == 1:
                            # If we want a return value, raise an error
                            raise RuntimeError (f"Failed to read with command '{tx_str}'.{e}")
                        else:
                            # If we are setting something, just warn the user
                            print(("Qontroller.issue_command: Warning: "
                                   "Failed to write with command '{tx_str}'. {e}"))
                            return None
                                

        def send_binary(self, cmd, raw=False):

                tx_str = cmd.binary() if not raw else cmd
                self.transmit(tx_str, binary_mode = True)

                n_lines_requested = 2**31
                target_errors=None
                output_regex=r'(.*)'
                special_timeout = None
            
             # Function to retry this command (in case of comms error)
                def retry_function():
                    return self.issue_binary_command(command_id, ch, BCAST, ALLCH, ADDM, RW,
                                                     ACT, DEXT, value_int, addr_id_num,
                                                     n_lines_requested, target_errors,
                                                     utput_regex, special_timeout)
                
                # Wait for response
                if RW==1 or ((RW==0 or ACT) and self.wait_for_responses):
                    result = self._issue_command_receive_response(retry_function,
                        n_lines_requested, target_errors,
                        output_regex, special_timeout)
                    
                    return result
            
            
        def send_ascii(self, cmd):

             n_lines_requested = 2**31
             target_errors=None
             output_regex=r'(.*)'
             special_timeout = None

             tx_str = cmd.ascii()
             self.transmit(tx_str)                    
                
             # Log it

             type = 'set' if cmd.type() == SET else 'get'
             
             self.log_append(type=type, value=cmd.data,
             id=cmd.idx, ch=cmd.addr, desc='Command: "'+tx_str+'".')


             # Function to retry this command (in case of comms error)
             def retry_function():
                 return self.send_ascii(cmd)


             # Wait for response
             if cmd.type() == GET or ((cmd.type() == SET) and self.wait_for_responses):
                 result = self._issue_command_receive_response(retry_function,
                     n_lines_requested, target_errors, output_regex, special_timeout)

                 return result
             
        
        def _issue_command_receive_response (self, retry_function, n_lines_requested=2**31, target_errors=None, output_regex=r'(.*)', special_timeout = None):
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
                
                i = 0
                while (True):
                    i += 1
                    
                    # Break conditions
                    if (RESPONSE_OK in lines):
                        break
                    elif (len(lines) >= n_lines_requested):
                        break
                    elif not all([err['id'] not in target_errors for err in errs]):
                        break
                    elif (time.time() - start_time > timeout):
                        if (time.time() - last_message_time >
                            self.inter_response_timeout):
                            break
                                
                    # Receive data
                    # if (random.randint(0, 100) % 2 == 0):
                    #       print(f"sleep, {self.device_id}", i)
                    #       time.sleep(1)
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
                        
                        for k in ks:
                                self[k] = vs[k]
                else:
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
        - Q8b
        """
        
        error_desc_dict = {**COMMON_ERRORS, **Qx_ERRORS}

        def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                
                self.n_chs = 0
                self.v_full = 0
                self.i_full = 0
                self.v = None                           # Channel voltages (direct access)
                self.i = None                           # Channel currents (direct access)
                self.vmax = None                        # Channel voltages (direct access)
                self.imax = None                        # Channel currents (direct access)
                self.binary_mode = False        # Communicate in binary
                
                
                # Populate parameters, if provided
                for para in ['binary_mode']:
                        try:
                                self.__setattr__(para, kwargs[para])
                        except KeyError:
                                continue
                
                
                # Get our full-scale voltage and current (VFULL, IFULL)
                try:
                        self.v_full = float(self.issue_command('vfull', operator = '?', n_lines_requested = 1, output_regex=r'(?:\+|-|)([\d\.]+) V')[0][0])
                except Exception as e:
                        raise RuntimeError("Unable to obtain VFULL from qontroller on port {:}. Error was {:}.".format(self.serial_port_name, e))
                try:
                        self.i_full = float(self.issue_command('ifull', operator = '?', n_lines_requested = 1, output_regex=r'(?:\+|-|)([\d\.]+) mA')[0][0])
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
                                        self.n_chs = int(self.issue_command('nchan', operator = '?', n_lines_requested = 1, target_errors = [10], output_regex = r'(\d+)\n')[0][0])
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
        
                regex = r'((?:\+|-){0,1}[\d\.]+)'
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
                        result = self.issue_binary_command(CMD_CODES[para.upper()], RW=1, ALLCH=1, BCAST=0, n_lines_requested = self.n_chs, output_regex = r'(?:\+|-|)([\d\.]+)', special_timeout = 2*self.response_timeout)
                else:
                        result = self.issue_command(para+'all', operator = '?', n_lines_requested = self.n_chs, output_regex = r'(?:\+|-|)([\d\.]+)', special_timeout = 2*self.response_timeout)
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
                self.v = None                           # Channel voltages (direct access)
                self.x = None                           # Channel positions (direct access)
                self.vmax = None                        # Channel voltages (direct access)
                self.imax = None                        # Channel currents (direct access)
                self.xmin = None                        # Channel minimum positions (direct access)
                self.xmax = None                        # Channel maximum positions (direct access)
                self.ustep = None                       # Channel microstep (direct access)
                self.mode = None                        # Channel mode (direct access)
                
                # Defaults
                
                self.binary_mode = False        # Communicate in binary
                
                
                # Populate parameters, if provided
                for para in ['binary_mode']:
                        try:
                                self.__setattr__(para, kwargs[para])
                        except KeyError:
                                continue
                
                
                # Get our full-scale voltage and current (VFULL, IFULL)
                try:
                        self.v_full = float(self.issue_command('vfull', operator = '?', n_lines_requested = 1, output_regex=r'(?:\+|-|)([\d\.]+).*')[0][0])
                except Exception as e:
                        raise RuntimeError("Unable to obtain VFULL from qontroller on port {:}. Error was {:}.".format(self.serial_port_name, e))
                try:
                        self.i_full = float(self.issue_command('ifull', operator = '?', n_lines_requested = 1, output_regex=r'(?:\+|-|)([\d\.]+) mA')[0][0])
                except:
                        raise RuntimeError("Unable to obtain IFULL from qontroller on port {:}.".format(self.serial_port_name))
                try:
                        self.x_full = float(self.issue_command('xfull', operator = '?', n_lines_requested = 1, output_regex=r'(?:\+|-|)([\d\.]+)')[0][0])
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
                                        self.n_chs = int(self.issue_command('nchan', operator = '?', n_lines_requested = 1, target_errors = [10], output_regex = r'(\d+)\n')[0][0])
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
                        result = self.issue_binary_command(CMD_CODES[para.upper()], ch=ch, RW=1, n_lines_requested = 1, output_regex = r'((?:\+|-){0,1}[\d\.]+)')
                else:
                        result = self.issue_command(para, ch = ch, operator = '?', n_lines_requested = 1, output_regex = r'((?:\+|-){0,1}[\d\.]+)')
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
                        result = self.issue_binary_command(CMD_CODES[para.upper()], RW=1, ALLCH=1, BCAST=0, n_lines_requested = self.n_chs, output_regex = r'(?:\+|-|)([\d\.]+)', special_timeout = 2*self.response_timeout)
                else:
                        result = self.issue_command(para+'all', operator = '?', n_lines_requested = self.n_chs, output_regex = r'(?:\+|-|)([\d\.]+)', special_timeout = 2*self.response_timeout)
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
                self.i = None                           # Channel currents (direct access)
                self.gain = None                        # Channel gain settings (direct access)
                self.binary_mode = False        # Communicate in binary
                
                
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
                                        self.n_chs = int(self.issue_command('nchan', operator = '?', n_lines_requested = 1, target_errors = [10], output_regex = r'(\d+)\n')[0][0])
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
                        regex = r'([\+-]?[\d\.]+)\s*([munpf]?)[VA]'
                else:
                        regex = r'([\+-]?[\d\.]+)'
                
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
                        result = self.issue_binary_command(CMD_CODES[para.upper()], RW=1, ALLCH=1, BCAST=0, n_lines_requested = self.n_chs, output_regex = r'(?:\+|-|)([\d\.]+)', special_timeout = 2*self.response_timeout)
                else:
                        result = self.issue_command(para+'all', operator = '?', n_lines_requested = self.n_chs, output_regex = r'x(?:\+|-|)([\d\.]+)', special_timeout = 2*self.response_timeout)
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
                                
                                
#                               sys.stdout.write("\r"+" "*40+"\r")
#                               sys.stdout.write('> ' + cmd.strip() + "\r\n")
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
        
        
