import os, pty, serial
import time
from enum import Enum
from collections import deque
from dataclasses import dataclass, field
from copy import deepcopy
import json


# Actions the program requests the VM to perform
Action = Enum('Action', ['QUEUE_OUT', 'QUEUE_OUT_MANY', 'RUN_CUSTOM','NOP'])


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
        
        


class VirtualModule:


    default_program = Program.from_json_file('default_program.json')
    

    def __init__(self, program=default_program):
        self.program = program
        self.port = VirtualPort(self)
        self.out = deepcopy(self.program.initial_out)
        self.port.in_waiting = len(self.out)
        self.cmd_cnt = {'all': 0}
        
    
    def _get_next_out(self):
        res = self.out.pop()
        self.port.in_waiting -= 1

        if isinstance(res, str):
            res =  res.encode('ascii')
            

        return res

    def _queue_out(self, i):
        self.out.append(i)
        self.port.in_waiting += 1


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
                return self.handle_write(args, kwargs)
            
            case VirtualPort.Cmd.CLOSE:
                self._inc_cmd_cnt(VirtualPort.Cmd.CLOSE)
                # TODO: implement
                

    def handle_write(self, args, kwargs):
        cmd = args[0].decode('ascii')
        response = self.program.lookup(cmd)
        self._inc_cmd_cnt(cmd)
        
        match response['action']:
            case Action.QUEUE_OUT:
                self._queue_out(response['data'])

            case Action.QUEUE_OUT_MANY:
                for i in reversed(response['data']):
                    self._queue_out(i)
                
                
            case Action.RUN_CUSTOM:
                return response['func'](cmd, self._read_cmd_cnt(cmd), self)
