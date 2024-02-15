from virtual_module import *
import json

class ProgramGenerator:

    def __init__(self, q):
        self.q = q

        self.prog = {}
        self.prog['name'] = 'Test Program'
        self.prog['data'] = {}
        self.prog['*'] = {
            'action': 'NOP',
            'data': ''
        }
        self.prog['initial_out'] = ['OK\n']

    def cmd(self, id, ch='', val=''):
        op = '=' if val != '' else '?'

        cs = f'{id}{ch}{op}{val}\n'
        res = self.q.issue_command(command_id=id, ch=ch, operator=op, value=val)

        action = 'QUEUE_OUT'
        if len(res) == 1:
            res = res[0][0]
        else:
            action = 'QUEUE_OUT_MANY'
            res = list(map(lambda x: x[0], res))
        
        
        self.prog['data'][cs] = {
            'action': action,
            'data': res
        }

    def write_prog(self, filename):
        with open(filename, 'w') as f:
            json.dump(self.prog, f, indent=4)
