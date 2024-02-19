import qontrol
from virtual_module import *



c = CustomHandler()

@c.register
def id_handler(cmd, cnt, vm):
    return vm._queue_out('Q8iv-0000')






p = Program.from_json_file('./progs/example.json', custom=c)
vm = VirtualModule(program=p)

q = qontrol.Qontroller(virtual_port=vm.port, response_timeout=0.200)


q.issue_command('id', operator='?')
q.issue_command('test', operator='?')


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

