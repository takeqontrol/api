import os, pty, serial
import time
from enum import Enum, auto
from collections import deque
from dataclasses import dataclass, field
from copy import deepcopy
import json
from pprint import pprint
from threading import Thread

# Actions the program requests the VM to perform
Action = Enum('Action', ['QUEUE_OUT', 'QUEUE_OUT_MANY', 'RUN_CUSTOM','NOP'])

class Action(Enum):
    QUEUE_OUT = auto()
    QUEUE_OUT_MANY = auto()
    RUN_CUSTOM = auto()
    NOP = auto()

    def __str__(self):
        return self.name


class VirtualPort:
    """Virtual Serial Port. Provides a bridge between the API and the virtual module."""

    # Different commands
    Cmd = Enum('Cmd', ['READ', 'WRITE', 'CLOSE', 'READLINE']) 

    def __init__(self, device):
        # Virtual module
        self.device = device

        # Port is always open. Maybe we want to change it in the future
        self.is_open = True
        self.in_waiting = 0

    def read(self, *args, **kwargs):
        return self.device.handle_cmd(VirtualPort.Cmd.READ, args, kwargs)

    def write(self, *args, **kwargs):
        return self.device.handle_cmd(VirtualPort.Cmd.WRITE, args, kwargs)

    def close(self, *args, **kwargs):
        return self.device.handle_cmd(VirtualPort.Cmd.CLOSE, args, kwargs)

    def readline(self, *args, **kwargs):
        return self.device.handle_cmd(VirtualPort.Cmd.READLINE, args, kwargs)



class CustomBehaviour:
    """
    Custom behaviour for programs.

    Allows the program to specify hooks to run for different commands.
    All hooks must be registered with this module before they can be ran.
    """
    def register(self, func):
        setattr(self, func.__name__, func)

    


@dataclass
class Program:
    """VirtualModule programs."""
    name: str = ""
    data: dict = field(default_factory= lambda: {})
    default: dict = field(default_factory= lambda: {})
    initial_out: list = field(default_factory= lambda: [])
    custom: CustomBehaviour = None

    def lookup(self, cmd):
        """Look up the response for a command."""
        return self.data.get(cmd, self.default)

    #########################################################
    # JSON Format 
    #########################################################
    @classmethod
    def from_json_file(cls, filename, custom=None):
        with open(filename) as f:
            program = json.load(f)
            return cls.from_json(program, custom)
            
    @classmethod
    def from_json(cls, json, custom=None):
        name = json['name']
        data = cls._build_data(json['data'], custom)
        default = cls._build_entry(json['*'], custom)
        initial_out = json['initial_out']

        return cls(name, data, default, initial_out, custom)
        
    @classmethod
    def _build_data(cls, data, custom=None):
        for v in data.values():
            if isinstance(v, list):
                for i in v:
                    cls._build_entry(i, custom)
                continue
            cls._build_entry(v, custom)

        return data

    @classmethod
    def _build_entry(cls, entry, custom=None):
        entry['action'] = Action[entry['action']]

        match entry['action']:
            case Action.RUN_CUSTOM:
                if custom is None:
                    raise ValueError("Program contains custom behaviour which was not provided!")
                entry['func'] = getattr(custom, entry['func'])
        
        return entry
        



@dataclass
class Response:
    delay: float
    data: list[str]

@dataclass
class LogEntry:
    cmd: str
    responses: list[Response] = field(default_factory= lambda: [])

class ProgramGenerator:

    def __init__(self, name, q, default=None):
        self.q = q

        self.prog = {}
        self.prog['name'] = name
        self.prog['data'] = {}
        self.prog['*'] = {
                'action': 'NOP',
                'data': ''
        } if default is None else default

        
        self.prog['initial_out'] = ['OK\n']

    def cmd(self, id, ch='', val=''):
        op = '=' if val != '' else '?'

        cs = f'{id}{ch}{op}{val}\n'
        res = self.q.issue_command(command_id=id, ch=ch, operator=op, value=val)

        action = str(Action.QUEUE_OUT)
        if len(res) == 1:
            res = res[0][0]
        else:
            action = str(Action.QUEUE_OUT_MANY)
            res = list(map(lambda x: x[0], res))
        
        
        self.prog['data'][cs] = {
            'action': action,
            'data': res
        }

    def _write_prog_entry(self, log_entry):
        data = []
        frames = []
        delays = []
        
        for res in log_entry.responses:
            action = Action.QUEUE_OUT_MANY
            data.extend(res.data)
            frames.append(len(res.data))
            delays.append(res.delay)


        if not log_entry.cmd in self.prog['data']:
                self.prog['data'][log_entry.cmd] = []


        # TODO: FIx this
        if len(data) == 1:
            self.prog['data'][log_entry.cmd].append({
                'action': str(Action.QUEUE_OUT),
                'data': data[0],
                'delay': delays[0]
            })
        else:
            if len(frames) == 1:
            
                self.prog['data'][log_entry.cmd].append({
                    'action': str(Action.QUEUE_OUT_MANY),
                    'data': data,
                    'delay': delays[0]
                })
            else:

                self.prog['data'][log_entry.cmd].append({
                'action': str(Action.QUEUE_OUT_MANY),
                'data': data,
                'divide': {
                    'frames': frames,
                    'delays': delays
                }
            })
                
        
    def parse_log(self, log):
        prev_time = 0
        parsed_log = deque()
        cmd_sent = 0
        
        for item in log:
            time_ms = 1000*item['proctime']
            type = item['type']
            desc = item['desc']

            if time_ms == prev_time:
                continue

    
            match type:
                case 'tx':
                    parsed_log.append(LogEntry(desc))
                    cmd_sent = time_ms
                case 'rcv':
                    cmd = parsed_log.pop()
                    cmd.responses.append(Response(time_ms - cmd_sent,
                                                  desc))
                    parsed_log.append(cmd)
                    cmd_sent = time_ms
                    
            prev_time = time_ms

        return parsed_log
      
        
    def from_log(self, log):
        parsed_log = self.parse_log(log)
        
        for i in parsed_log:
            self._write_prog_entry(i)
            
        

    def write_prog(self, filename):
        with open(filename, 'w') as f:
            json.dump(self.prog, f, indent=4)



class VirtualModule:


    default_program = Program.from_json_file('default_program.json')
    

    def __init__(self, program=default_program):
        self.program = program
        self.port = VirtualPort(self)
        self.out = deque()
        self.port.in_waiting = len(self.out)
        self.cmd_cnt = {'all': 0}
        self.outstanding = deque()
        
    
    def _get_next_out(self):
        res = self.out.popleft()
        self.port.in_waiting = len(self.out)
        
        if res is None:
            res = ' '            

        if isinstance(res, str):
            res =  res.encode('ascii')
            

        return res

    def _queue_out(self, i):
        self.out.append(i)
        self.port.in_waiting = len(self.out)


    def _inc_cmd_cnt(self, cmd):
        if not cmd in self.cmd_cnt:
            self.cmd_cnt[cmd] = 0

        self.cmd_cnt[cmd] += 1
        self.cmd_cnt['all'] += 1
        
    def _read_cmd_cnt(self, cmd):
        return self.cmd_cnt.get(cmd, 0)

    def handle_cmd(self, cmd, args, kwargs):
        match cmd:
            case VirtualPort.Cmd.READ:
                self._inc_cmd_cnt(VirtualPort.Cmd.READ)
                # TODO: implement
                
            case VirtualPort.Cmd.READLINE:
                self._inc_cmd_cnt(VirtualPort.Cmd.READLINE)
                return self._get_next_out()
            
            case VirtualPort.Cmd.WRITE:
                self._inc_cmd_cnt(VirtualPort.Cmd.WRITE)
                t = Thread(target=self.handle_write, args=(args, kwargs))
                t.start()
                #return self.handle_write(args, kwargs)
            
            case VirtualPort.Cmd.CLOSE:
                self._inc_cmd_cnt(VirtualPort.Cmd.CLOSE)
                # TODO: implement

             

    def handle_write(self, args, kwargs):
        cmd = args[0].decode('ascii')
        self._inc_cmd_cnt(cmd)
        
        responses = self.program.lookup(cmd)

        try:
            response = responses[self._read_cmd_cnt(cmd)-1]
        except KeyError:
            return
        
        
        match response['action']:
            case Action.QUEUE_OUT:
                delay = response['delay']
                #time.sleep(delay / 1000)
                sleep(delay)
                self._queue_out(response['data'])

            case Action.QUEUE_OUT_MANY:
                if 'divide' in response:
                    parts = partition(response['data'],
                                      response['divide']['frames'])
                    delays = response['divide']['delays']

                    for d, p in zip(delays, parts):
                        #time.sleep(d / 1000)
                        sleep(d)
                        for i in p:
                            self._queue_out(i)

                else:
                    #time.sleep(d / 1000)
                    sleep(response['delay'])
                    for i in response['data']:
                        self._queue_out(i)
                
                
            case Action.RUN_CUSTOM:
                return response['func'](cmd, self._read_cmd_cnt(cmd), self)



def partition(xs, frames):
    chunks = []
    current_idx = 0
    for i in frames:
        chunks.append(xs[current_idx:current_idx+i])
        current_idx = current_idx+i
    
    return chunks          

def sleep(ms):
    now = time.clock_gettime_ns(time.CLOCK_PROCESS_CPUTIME_ID) / 1e+6
    end =  now + ms
    #print(f'now = {now} end = {end} diff = {end - now}')
    while now < end:
        now = time.clock_gettime_ns(time.CLOCK_PROCESS_CPUTIME_ID)  / 1e+6
    #print(f'>>> {now}  {now - end}')
