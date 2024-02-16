import qontrol
import serial
import serial.tools.list_ports
from virtual_module import *
from pprint import pprint

N_CH = 8

def cmd(id, ch='', val=''):
    
    op = '=' if val != '' else '?'

    
    #print(f'> {id}{ch}{op}{val}')
    res = q.issue_command(command_id=id, ch=ch, operator=op, value=val)
    #print(f'< {res}')
            
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


p = Program.from_json_file('./progs/test.json', custom=c)
vm = VirtualModule(program=p)

q = qontrol.Qontroller(virtual_port=vm.port)

#########################################################
# Commands
#########################################################

cmd('id')
cmd('lifetime')
cmd('firmware')
cmd('vall')
cmd('iall')
cmd('vall')


def print_log(log):
    t = 0
    for item in log:
        time_ms = 1000*item['proctime']
        type = item['type']
        desc = item['desc']

        if isinstance(desc, str):
            desc = desc.strip()

        print(f'{time_ms} {type} {desc} ')


print_log(q.log)

#pprint(vm.cmd_cnt, indent=4)

