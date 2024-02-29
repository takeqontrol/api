import time
import json
import logging
import pdb
import inspect
from enum import Enum, auto
from collections import deque
from dataclasses import dataclass, field
from threading import Thread


formatter = logging.Formatter('%(levelname)s: %(message)s')
log = logging.getLogger('virtual_module')

ch = logging.StreamHandler()
ch.setLevel(logging.ERROR)
ch.setFormatter(formatter)
log.addHandler(ch)


def error(msg):
    log.error(msg)
    exit(1)
    


class CustomHandler:
    """Custom behaviour for programs.

    Allows the program to specify handlers to run for different commands.
    All handlers must be registered with this module before they can be ran.
    """
    def register(self, func):
        """Registers a custom command handler.

        Handlers must accept 3 parameters:
          cmd - The command string
          cnt - How many times the command was called
          vm  - A reference to the virtual module

        Note that this can be used as a decorator.
        E.g.:

          c = CustomHandler()

          @c.register
          def foo(cmd, cnt, vm):
              pass
        """
        args = inspect.getfullargspec(func).args

        if len(args) != 3:
            error('Custom functions must accept 3 arguments!')
        
        setattr(self, func.__name__, func)


class VirtualPort:
    """Provides a bridge between a Qontroller and a virtual device.

    The interface of this class mimics Serial from pyserial.
    When a method is called it simply notifies the virtual module
    by passing a command and lets it handle everything. 
    """

    # Events passed to the virtual module
    Event = Enum('Event', ['READ', 'WRITE', 'CLOSE', 'READLINE']) 

    def __init__(self, device):
        # Virtual module
        self.device = device

        # Port is always open. Maybe we want to change it in the future
        self.is_open = True

        # Number of items ready to be read
        # This is updated by the virtual module
        self.in_waiting = 0

    def read(self, *args, **kwargs):
        """Notify the VM that a READ event occured."""
        return self.device.handle_event(VirtualPort.Event.READ, args, kwargs)

    def readline(self, *args, **kwargs):
        """Notify the VM that a READLINE event occured."""
        return self.device.handle_event(VirtualPort.Event.READLINE, args, kwargs)

    def write(self, *args, **kwargs):
        """Notify the VM that a WRITE event occured."""
        return self.device.handle_event(VirtualPort.Event.WRITE, args, kwargs)

    def close(self, *args, **kwargs):
        """Notify the VM that a CLOSE event occured."""
        return self.device.handle_event(VirtualPort.Event.CLOSE, args, kwargs)

    
class Action(Enum):
    """
    Represents actions the virtual module needs to perform. 
    """

    # Write a single message to the output queue
    QUEUE_OUT = auto()

    # Write a list of messages to the output queue
    QUEUE_OUT_MANY = auto()

    # Run a custom function
    # The function must be registered in a custom behaviour
    RUN_CUSTOM = auto()

    # No operation
    NOP = auto()

    def __str__(self):
        """Returns the enum name as a str"""
        return self.name

    @classmethod
    def list(cls):
        """Returns a list of all enums"""
        return list(map(lambda c: str(c), cls))

class VirtualModule:
    """Emulates a real device.

x
    The qontroller interacts with the virtual module (VM) through a virtual port. 
    The VM is configured by programs (see Program class) which tell it
    how to behave when it sees a certain command.

                                ┌─────────────────┐
                                │  VirtualModule  │
                                │                 │
     ┌────────────┐             │  ┌───────────┐  │
     │ Qontroller │◄────────────┼─►│VirtualPort│  │
     └────────────┘             │  └───────────┘  │
                                │                 │
                                │  ┌───────────┐  │
                                │  │  Program  │  │
                                │  └───────────┘  │
                                │                 │
                                └─────────────────┘

    The module is a simple state machine. It receives an event
    from the port (currently only READLINE and WRITE are handled)
    and then responds accordingly.

    It keeps a queue of out messages which are ready to be sent
    to the qontroller when a READLINE event is raised.

    When it receives a WRITE event it checks if the command that was sent
    is in the current program. If it is then it carries out the specified action
    (see Action Enum). Note that if the program contains a delay, the module
    will need to sleep before carrying out its action. If the Qontroller and the VM
    run on the same thread it won't be possible to emulate the delay, as the
    qontroller needs to run while the module is sleeping. Because of that the WRITE
    handler runs on a separate thread. 

    Possible actions are:
    
         - QUEUE_OUT : Put on the out queue the data specified in the program.
         
         - QUEUE_OUT_MANY: This is the same as QUEUE_OUT but the data  
           is a list, not a single item.

           Sometimes the device might respond to a command in chunks.
           To emulate this the program can specify a 'divide' component
           which lets the module know how it needs to divide its response .
           Note that each chunk will also come with its own delay.

        - RUN_CUSTOM: Run a custom handler.

        - NOP: Do nothing. 
    """

    def __init__(self, program):
        """Create a VirtualModule instance.

        Args:
            program (Program): virtual module program
 
        """
        # Current program
        self.program = program

        # Virtual port 
        self.port = VirtualPort(self)

        # Queue of messages which are ready to be sent
        # Note: Thread safe when reading/writing to/from opposite ends
        self.out = deque()

        # Initialise port's in_waiting count
        self.port.in_waiting = len(self.out)

        # To keep track of how many times each command was called
        self.cmd_cnt = {'all': 0}
        
        
    
    def _get_next_out(self):
        """Return the next item from the out queue."""
        res = self.out.popleft()
        self.port.in_waiting -= 1

        # If the response is a string
        # we need to encode it
        if isinstance(res, str):
            res = res.encode('ascii')
            
        return res

    def _queue_out(self, msg):
        """Put a message in the out queue.

        Args:
           msg - message
           
        """
        self.out.append(msg)
        self.port.in_waiting += 1


    def _inc_cmd_cnt(self, cmd):
        """Increment the command counter.

        Args:
           cmd (str) - Command to increment the counter for
           
        """
        # If the cmd hasn't been seen before
        if not cmd in self.cmd_cnt:
            self.cmd_cnt[cmd] = 0

        self.cmd_cnt[cmd] += 1

        # Also keep track of the total
        # number of commands
        self.cmd_cnt['all'] += 1
        
    def _read_cmd_cnt(self, cmd):
        """Return the count for a command.

        Args:
            cmd - Command
            
        """
        return self.cmd_cnt.get(cmd, 0)

    def handle_event(self, event, args, kwargs):
        """Handle a port event.

        Args:
            event  - The event that occured
            args   - args passed from the qontroller
            kwargs - kwargs passed from the qontroller
        """
        match event:
            case VirtualPort.Event.READLINE:
                self._inc_cmd_cnt(VirtualPort.Event.READLINE)

                # Send a message from the out queue
                return self._get_next_out()
            
            case VirtualPort.Event.WRITE:
                self._inc_cmd_cnt(VirtualPort.Event.WRITE)
                # Start the write handler in a new thread
                t = Thread(target=self.handle_write_event, args=(args, kwargs))
                t.start()
            
            case VirtualPort.Event.CLOSE:
                self._inc_cmd_cnt(VirtualPort.Event.CLOSE)
                # TODO: implement

            case VirtualPort.Event.READ:
                self._inc_cmd_cnt(VirtualPort.Event.READ)
                # TODO: implement

             

    def handle_write_event(self, args, kwargs):
        """Handle write event from port.

         Args:
            args   - args passed from the qontroller
            kwargs - kwargs passed from the qontroller
        """

        # If command is binary
        if args[0][0] > 0x80:
            cmd = args[0].hex()
        else:
            cmd = args[0].decode('ascii')

        # Get responses from program
        cmd_data = self.program[cmd]

            
        self._inc_cmd_cnt(cmd)
        
        
        responses = cmd_data['entries']
        
        # # TODO: TEMP fix for default
        # # I need to figure out what is wrong
        # if not isinstance(responses, list):
        #     responses = [responses]
        
        # If there no responses there is nothing to do
        if not responses:
            return 
        
        # Every command can have multiple responses
        # if we can, choose the one that corresponds
        # to the current command count
        index = (self._read_cmd_cnt(cmd) - 1) % len(responses)
        response = responses[index]

        match response['action']:
            
            case Action.QUEUE_OUT:
                delay = response['delay']
                data = response['data']
                
                sleep(delay)
                self._queue_out(data)

            case Action.QUEUE_OUT_MANY:
                # Check if we need to segment the response
                if 'divide' in response:

                    # We do, so partition the data into chunks
                    parts = partition(response['data'],
                                      response['divide']['frames'])
                    
                    delays = response['divide']['delays']

                    # For every partition
                    for d, p in zip(delays, parts):
                        # Sleep and the queue responses
                        sleep(d)
                        for i in p:
                            self._queue_out(i)

                else:
                    # We don't need to partition
                    sleep(response['delay'])
                    for i in response['data']:
                        self._queue_out(i)
                
                
            case Action.RUN_CUSTOM:
                # Run the custom handler
                return response['func'](cmd, self._read_cmd_cnt(cmd), self)


    


@dataclass
class Program:
    """Virtual Module Program.

    Programs are dictionaries that map commands to responses.

    They can be written as python dicts or json files.

    Program structure:

      name        - Program name
      data        - Command to entry map
      *           - Default entry. Used for unknown commands
      initial_out - Initial contents of output queue


    Entry structure:
      action - Action for the VM.
               Determines other entry attributes

      QUEUE_OUT:
        data  - single message
        delay - Delay in ms (float

      QUEUE_OUT_MANY:
        data - list of messages

        divide [optional] - Specifies segmentation layout
          frames - Partition lengths (list[int])
          delays - Partition delays  (list[float])

        delay [if divide not specified] - Delay in ms (float)

      RUN_CUSTOM:
        func - Handler function

      NOP:
        data - Ignored
    """

    # Program name
    name: str = ""

    # The dictionary data
    data: dict = field(default_factory= lambda: {})

    # Initial output queue
    initial_out: list = field(default_factory= lambda: [])

    # Custom handlers
    custom: CustomHandler = None

    # Mapping commands to indices for quick lookup
    cmd2idx: dict = field(default_factory= lambda: {})


    def __getitem__(self, cmd):
        """Look up the response for a command."""
        if cmd not in self.cmd2idx:
            cmd = '*'
        
        i = self.cmd2idx[cmd]
        
        return self.data[i]

    def commands(self):
        return list(self.cmd2idx.keys())

        

    #########################################################
    # JSON Format 
    #########################################################
    @classmethod
    def from_json_file(cls, filename, custom=None):
        """Create a program from a json file.

        Args:
            filename (str)    - Filename
            custom (CustomHandler, optional) - custom handlers
        """
        with open(filename, 'r') as f:
            try: 
                program = json.load(f)
            except Exception as e:
                log.exception(f'Loading {filename}')
                exit(1)
                
            return cls.from_dict(program, custom)
            
    @classmethod
    def from_dict(cls, prog, custom=None):
        """Create a program from a dictionary .

        Args:
            prog (dict) - Program dict
            custom (CustomHandler, optional) - custom handlers
        """
        try:
            name = prog['name']
            data, cmd2idx = cls._parse_data(prog['data'], custom)
            # default = cls._parse_data(prog['*'], custom)
            initial_out = prog['initial_out']
            
            
        except Exception:
            log.exception('Creating program from json data')
  

        return cls(name, data, initial_out, custom, cmd2idx)


    @classmethod
    def _parse_data(cls, data, custom=None):
        """Parse the program data"""

        cmd2idx = {}

        for i, cmd_entry in enumerate(data):

            # Save the command index
            cmd2idx[cmd_entry['cmd']] = i

            
            for entry in cmd_entry['entries']:
                cls._parse_entry(entry, custom)

        return data, cmd2idx

    @classmethod
    def _parse_entry(cls, entry, custom=None):
        """Parse a single command entry.
        """

        # Convert the action to its enum
        action = Action[entry['action']]
        entry['action'] = action

        # In case of RUN_CUSTOM
        # load the appropriate handler
        if action == Action.RUN_CUSTOM:
            func = getattr(custom, entry['func'], None)

            if func is None:
                error(f"Can't find custom behaviour {entry['func']}!")
                    
            entry['func'] = func
                
        return entry



@dataclass
class Response:
    delay: float
    data: list[str]

@dataclass
class LogEntry:
    cmd: str
    encoding: str
    responses: list[Response] = field(default_factory= lambda: [])
        

class ProgramGenerator:
    """Generates a Program from a Qontroller log"""


    def __init__(self, name, log):
        self.prog = {}
        self.prog['name'] = name
        self.prog['data'] = []
        self.prog['initial_out'] = ['OK\n']

        self.seen_cmds = set()

        self.parsed_log = self._parse_log(log)

        for i in self.parsed_log:
            self._gen_entry(i)

        # Add the default entry for unknown commands
        self.prog['data'].append(
             {
              "cmd": "*",
              "encoding": "ascii",
              "entries": [
                {
                    "action": "QUEUE_OUT",
                    "data": "E10:00",
                    "delay": 0.0
                }
              ]
            }
        )



    def _parse_log(self, log):
        """Parse a Qontroller log.

        Args:
            log - Qontroller log
            
        Returns:
            Parsed log (deque of LogEntry objects)
        """
        parsed_log = deque()
        # Time of previous command
        # Used for calculating delays
        prev_time = 0

        for item in log:
            time_ms = 1000*item['proctime']
            cmd_type = item['type']
            desc = item['desc']

            encoding = 'ascii'

            match cmd_type:
                case 'tx':
                    # If cmd was tx append a new log entry
                    if isinstance(item['raw'], bytes):
                        encoding = 'binary'
                    
                    parsed_log.append(LogEntry(desc, encoding))
                    
                case 'rcv':
                    # If cmd was rcv update the last entry
                    cmd = parsed_log.pop()
                    cmd.responses.append(Response(time_ms - prev_time,
                                                  desc))
                    parsed_log.append(cmd)

                case 'err':
                    # If response was an error add the raw data
                    cmd = parsed_log.pop()
                    cmd.responses.append(Response(time_ms - prev_time,
                                                  [item['raw']]))
                    parsed_log.append(cmd)
                    
            prev_time = time_ms

        return parsed_log

    def find_cmd_data(self, cmd):
        for entry in self.prog['data']:
            if cmd == entry['cmd']:
                return entry['entries']

        return None


    def _gen_entry(self, log_entry):
        """Generate a program entry

        args:
            log_entry - LogEntry object
        """
        data = []
        frames = []
        delays = []

        # Collect the reponse data
        for res in log_entry.responses:
            data.extend(res.data)
            frames.append(len(res.data))
            delays.append(res.delay)

        
        
        # Initialise cmd entry
        if not log_entry.cmd in self.seen_cmds:
            self.prog['data'].append({
                "cmd": log_entry.cmd,
                "encoding": log_entry.encoding,
                "entries": []
            })

            cmd_data = self.prog['data'][-1]['entries']
            self.seen_cmds.add(log_entry.cmd)
        else:
            cmd_data = self.find_cmd_data(log_entry.cmd)
                

        # Determine action and data type
        action = str(Action.QUEUE_OUT) if len(data) == 1 else str(Action.QUEUE_OUT_MANY)
        data = data[0] if len(data) == 1 else data
        
        # Add common attributes
        cmd_data.append({
            'action': action,
            'data': data,
        })

        if len(frames) == 1:
            # If we have only one frame we don't segment
            # So we have a single delay
            cmd_data[-1]['delay'] = delays[0]
         
        else:
            # We need to segment, so add divide component
            cmd_data[-1]['divide'] = {
                'frames': frames,
                'delays': delays
            }
        
    def write(self, filename):
        """Write a program to a json file.

        args:
             filename - File to write
        """
        with open(filename, 'w') as f:
            json.dump(self.prog, f, indent=4)

    def gen(self):
        """Generate a program.

        returns:
             Program object
        """
        return Program.from_dict(self.prog)


############################################################################
# Utility functions
############################################################################




def partition(xs, frames):
    """Partition a list into frames.

    args:
        xs (list) - list to partition
        frames    - chunks to partition it into
    """
    chunks = []
    current_idx = 0
    for i in frames:
        chunks.append(xs[current_idx:current_idx+i])
        current_idx = current_idx+i
    
    return chunks          

def sleep(ms):
    """Busy sleep.

    args:
        ms - Milliseconds to sleep
    """
    now = time.clock_gettime_ns(time.CLOCK_PROCESS_CPUTIME_ID) / 1e+6
    end =  now + ms

    while now < end:
        now = time.clock_gettime_ns(time.CLOCK_PROCESS_CPUTIME_ID)  / 1e+6

