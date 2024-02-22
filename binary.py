from qontrol import *
from virtual_module import *
import timeit

p = Program.from_json_file('progs/test.json')
vm = VirtualModule(p)
q = Qontroller(virtual_port=vm.port)


all_pass = True


def compare(cmd):

    args = {}
    for i in HeaderId:
        if i == BIN or i == PBIT:
            continue
        
        if i in cmd.header:
            args[str(i)] = 1
        else:
            args[str(i)] = 0

    args['value_int'] = cmd.data
    args['addr_id_num'] = cmd.addr_id
    expected = q.issue_binary_command(cmd.idx.value,
                                      ch=cmd.addr,
                                      **args)

    print(f'{cmd.binary() == expected} {expected} | {cmd.binary()}')

    all_pass =  cmd.binary() == expected
        
    
    return cmd.binary() == expected


for i in range(8):
    compare(Command(GET, V, i))
    compare(Command(SET, V, i, data=i))
    

compare(Command(GET, V, header={ALLCH}))
compare(Command(GET, I, header={ALLCH, BCAST}))

compare(Command(SET, V, data=100, header={ALLCH}))


compare(Command(GET, V, data=[1], header={DEXT}))
compare(Command(GET, I, data=[1, 5, 90], header={DEXT}))

for cmd in Index:
    compare(Command(GET, cmd))
    compare(Command(GET, cmd, header={ALLCH}))


compare(Command(GET, V, i, addr_id=5, header={ADDM}))
    
print(f'all_pass = {all_pass}')






def test():
    q.issue_binary_command(V.value, ch=0)

c = Command(GET, V, 0)
def test2():
     c.binary()

    
t =  timeit.timeit('test()', setup='from __main__ import test')
t2 =  timeit.timeit('test2()', setup='from __main__ import test2')

print(t)
print(t2)
