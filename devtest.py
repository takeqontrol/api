import qontrol
from virtual_module import *
from pprint import pprint

N_CH = 8

def cmd(q, id, ch='', val=''):
    
    op = '=' if val != '' else '?'

    
    #print(f'> {id}{ch}{op}{val}')
    res = q.issue_command(command_id=id, ch=ch, operator=op, value=val)
    #print(f'< {res}')
            
#########################################################
# Program
#########################################################
c = CustomHandler()

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


q = qontrol.Qontroller(virtual_port=vm.port, response_timeout=0.200)


# #########################################################
# # Commands
# #########################################################

# cmd(q, 'id')
# cmd(q, 'lifetime')
# cmd(q, 'firmware')
# cmd(q, 'vall')
# cmd(q, 'iall')
# cmd(q, 'vall')
# cmd(q, 'iall')

# for ch in range(N_CH):
#     cmd(q, f'v{ch}=0.1')
#     cmd(q, f'v{ch}?')
#     cmd(q, f'vcal{ch}?')


#     cmd(q, f'i{ch}=0')
#     cmd(q, f'i{ch}')
#     cmd(q, f'ical{ch}')
    
# cmd(q, 'nchan')
# cmd(q, 'nvmall')

cmd(q, 'log')


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

