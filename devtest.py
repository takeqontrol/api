import qontrol
import serial
import serial.tools.list_ports
from virtual_module import *
from pprint import pprint



def cmd(id, ch='', val=''):
    
    op = '=' if val != '' else '?'

    
    print(f'> {id}{ch}{op}{val}')
    res = q.issue_command(command_id=id, ch=ch, operator=op, value=val)
    print(f'< {res}')
            



p = Program()



print('> create qontroller')

c = CustomBehaviour()

@c.register
def id_custom(cmd, cnt, vm):
    if cnt > 3:
        return vm._queue_out('bla bla')
    else:
        return vm._queue_out('Q8iv-0000')




p = Program.from_json_file('custom_program.json', custom=c)

vm = VirtualModule(program=p)
q = qontrol.Qontroller(virtual_port=vm.port, timeout=1000)


cmd('id')

cmd('nupall')
cmd('id')
cmd('id')
cmd('id')

# cmd('firmware')
# cmd('log')
# cmd('nup', ch='all')

# for i in range(N_CH):
#     cmd('v', ch=i)

# for i in range(N_CH):
#     cmd('i', ch=i)



# cmd('v', ch=1, val=0.2)
# cmd('v', ch=1)
# cmd('v',ch='all')


#pprint(vm.cmd_cnt, indent=4)
