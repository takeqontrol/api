import os, pty, serial
import time
from enum import Enum
from collections import deque
from dataclasses import dataclass

class VirtualPort:

    Cmd = Enum('Cmd', ['READ', 'WRITE', 'CLOSE', 'READLINE']) 

    def __init__(self, device):
        self.device = device
        
        self.is_open = True
        self.in_waiting = 0
        
        print('Crerated virtual port')

    def read(self, *args, **kwargs):
        print('read', args, kwargs)
        return self.device.handle_cmd(VirtualPort.Cmd.READ, args, kwargs)

    def write(self, *args, **kwargs):
        print('write', args, **kwargs)
        return self.device.handle_cmd(VirtualPort.Cmd.WRITE, args, kwargs)

    def close(self, *args, **kwargs):
        print('close', args, **kwargs)
        return self.device.handle_cmd(VirtualPort.Cmd.CLOSE, args, kwargs)

    def readline(self, *args, **kwargs):
        print('readline', args, kwargs)
        return self.device.handle_cmd(VirtualPort.Cmd.READLINE, args, kwargs)


Action = Enum('Action', ['QUEUE_OUT', 'NOP'])
# Add to the global name space
globals().update(Action.__members__)



@dataclass
class Program:
    """VirtualModule programs."""
    name: str
    data: dict
    default: dict

    def lookup(self, cmd):
        return self.data.get(cmd, self.default)



class VirtualModule:

    default_program = Program('Defauilt Virtual Module',
        {
             'nup=0\n': {
                'action': QUEUE_OUT,
                'data': 'OK\n'
             },
 
             'nupall?\n': {
                'action': QUEUE_OUT,
                'data': 'Q8iv-0000: 0\n'
             }
        },

        # Default 
        {
         'action': NOP,
         'data': ''
        }       
    )
    

    def __init__(self, program=default_program):
        self.program = program
        self.port = VirtualPort(self)
        self.out = ['OK\n']
        self.port.in_waiting = len(self.out)
        
    
    def _get_next_out(self):
        res = self.out.pop()
        self.port.in_waiting -= 1

        return res.encode('ascii')

    def _queue_out(self, i):
        self.out.append(i)
        self.port.in_waiting += 1
        

    def handle_cmd(self, cmd, args, kwargs):
        match cmd:
            case VirtualPort.Cmd.READ:
                pass
            case VirtualPort.Cmd.READLINE:
                return self._get_next_out()
            case VirtualPort.Cmd.WRITE:
                return self.handle_write(args, kwargs)
            case VirtualPort.Cmd.CLOSE:
                pass



    def handle_write(self, args, kwargs):
        cmd = args[0].decode('ascii')

        #response = p.get(cmd, default)
        response = self.program.lookup(cmd)
        
        match response['action']:
            case QUEUE_OUT:
                self._queue_out(response['data'])
