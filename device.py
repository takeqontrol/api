import qontrol
import sys
from virtual_module import *
from pprint import pprint


N_CH = 8
dev_port='/dev/tty.usbserial-FT3Z4WXD'

def cmd(q, id, ch='', val=''):
    
    op = '=' if val != '' else '?'

    
    #print(f'> {id}{ch}{op}{val}')
    res = q.issue_command(command_id=id, ch=ch, operator=op, value=val)
    #print(f'< {res}')


def pc_1():
    vm = VirtualModule()
    q = qontrol.Qontroller(serial_port_name=dev_port)


    pc = ProgramGenerator('Device Program', q)

    pc.cmd('nup', val=0)
    pc.cmd('nupall')
    pc.cmd('lifetime')
    pc.cmd('id')
    pc.cmd('firmware')
    pc.cmd('log')


    for i in range(N_CH):
        pc.cmd('v', ch=i)

    for i in range(N_CH):
        pc.cmd('i', ch=i)



    pc.cmd('v', ch=1, val=0.2)
    pc.cmd('v', ch=1)
    pc.cmd('v',ch='all')


    pc.write_prog(sys.argv[1])


    
def pc_2():
    vm = VirtualModule()
    q = qontrol.Qontroller(serial_port_name=dev_port)
    pc = ProgramGenerator('Device Program', q)



    cmd(q, 'id')
    cmd(q, 'lifetime')
    cmd(q, 'firmware')
    cmd(q, 'vall')
    cmd(q, 'iall')
    cmd(q, 'vall')

    
    pc.from_log(q.log)
    pc.write_prog(sys.argv[1])
    print_log(q.log)


def print_log(log):
    t = 0
    
    for item in log:
        time_ms = 1000*item['proctime']
        type = item['type']
        desc = item['desc']

        if isinstance(desc, str):
            desc = desc.strip()

        print(f'{time_ms} {type} {desc} ')





if __name__ == '__main__':
    pc_2()