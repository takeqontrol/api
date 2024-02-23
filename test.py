import pytest
import re
from qontrol import Qontroller, generic_log_handler
from virtual_module import *
from glob import glob

cmd_re = re.compile(r'([a-zA-Z0-9]*)(\?|=)(.*)')



c = CustomHandler()

@c.register
def id_handler(cmd, cnt, vm):
    return vm._queue_out('Q8iv-0000')


def log_handler():
    """
    Log handler that raises an exception
    when the Qontroller encounters an error.
    """
    def _generic_log_handler(err_dict):
        if err_dict['type'] == 'err':
            print('raised an error')
            raise RuntimeError(err_dict['raw'])

        
    return _generic_log_handler



def params():
    """Generate test parameters from all programs"""
    program_files= glob('progs/*.json')

    ret = []
    for pf in program_files:
        program = Program.from_json_file(pf, custom=c)
        vm = VirtualModule(program)
        q = Qontroller(virtual_port=vm.port, response_timeout=0.4)
        q.log_handler = log_handler()

        for cmd in program.commands():
            ret.append((pf, program, q, cmd))

    return ret



class TestCommandFromProgram:
    """Class for tests generated from VM programs."""

    @pytest.mark.parametrize("f, p, q, cmd", params())
    def test_cmd(self, f, p, q, cmd):

        # Parse the command
        action, expected = self.parse_command(p[cmd]['entries'][0])

        try:
            if p[cmd]['encoding'] == 'binary':
                res = q.send_binary(bytes.fromhex(cmd), raw=True)
                print(res)
            else:
            
                c, op, val = cmd_re.search(cmd.strip()).groups()
                res = q.issue_command(c, operator=op, value=val)
            
        except RuntimeError as e:
            # The log_handler will raise an exception
            # when the qontrollers encounters an error
            # Pass test if thats expected
            assert (str(e) == expected['data']) or (str(e) in expected['data'])
            return

        match action:
            case Action.QUEUE_OUT:
                # result is 1 element
                assert res[0] == (expected['data'],)
                
            case Action.QUEUE_OUT_MANY:
                # Result is an array
                exp = list(map(lambda x: (x,), expected['data']))
                assert res == exp
                
    

    def parse_command(self, cmd):
        action = cmd['action']

        res = {}
        match action:

            case Action.QUEUE_OUT | Action.NOP:
                res['data'] = cmd['data'].strip('\n')
                
            case Action.QUEUE_OUT_MANY:
                res['data'] = list(map(lambda x: x.strip('\n'), cmd['data']))

            case Action.RUN_CUSTOM:
                res['func'] = cmd['func']
                res['data'] = ''
        
        return action, res


