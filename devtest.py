import qontrol
import serial
import serial.tools.list_ports
from virtual_module import *
from pprint import pprint

N_CH = 8

def cmd(id, ch='', val=''):
    
    op = '=' if val != '' else '?'

    
    print(f'> {id}{ch}{op}{val}')
    res = q.issue_command(command_id=id, ch=ch, operator=op, value=val)
    print(f'< {res}')
            
#########################################################
# Program
#########################################################
c = CustomBehaviour()

@c.register
def id_custom(cmd, cnt, vm):
    if cnt > 3:
        return vm._queue_out('bla bla')
    else:
        return vm._queue_out('Q8iv-0000')


@c.register
def handle_wildcard(cmd, cnt, vm):
    return vm._queue_out(f'idk how to handle {cmd}')


p = Program.from_json_file('test.json', custom=c)
vm = VirtualModule(program=p)

q = qontrol.Qontroller(virtual_port=vm.port)

#########################################################
# Commands
#########################################################

cmd('id')

cmd('lifetime')
cmd('id')
cmd('id')
cmd('id')

cmd('firmware')


cmd('log')


for i in range(N_CH):
     cmd('v', ch=i)

for i in range(N_CH):
     cmd('i', ch=i)

cmd('v', ch=1, val=0.2)
cmd('vall')

#pprint(vm.cmd_cnt, indent=4)
