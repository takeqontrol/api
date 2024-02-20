import pytest
import re
from qontrol import Qontroller
from virtual_module import *
from glob import glob

cmd_re = re.compile(r'([a-zA-Z0-9]+)(\?|=)(.*)')



c = CustomHandler()

@c.register
def id_handler(cmd, cnt, vm):
    return vm._queue_out('Q8iv-0000')


def params():
    """Generate test parameters from all programs"""
    program_files= glob('progs/*.json')

    ret = []
    for pf in program_files:
        program = Program.from_json_file(pf, custom=c)
        vm = VirtualModule(program)
        q = Qontroller(virtual_port=vm.port, response_timeout=0.4)

        for cmd in program.commands():
            ret.append((pf, program, q, cmd))

    return ret



class TestCommandFromProgram:
    """Class for tests generated from VM programs."""

    @pytest.mark.parametrize("f, p, q, cmd", params())
    def test_cmd(self, f, p, q, cmd):
        # Parse the command
        c, op, val = cmd_re.search(cmd.strip()).groups()

        # Run the command 
        res = q.issue_command(c, operator=op, value=val)
        
        
        match p[cmd][0]['action']:
            case Action.QUEUE_OUT:
                # result is 1 element
                assert res[0] == (p[cmd][0]['data'].strip(),)
                
            case Action.QUEUE_OUT_MANY:
                # Result is an array
                expected = list(map(lambda x: (x.strip(),), p[cmd][0]['data']))
                assert res == expected
    

