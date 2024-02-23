from qontrol import *
from virtual_module import *
import timeit
from random import randint
import math


p = Program.from_json_file('progs/binary_test.json')
vm = VirtualModule(p)
q = Qontroller(virtual_port=vm.port, response_timeout=0.5)

# dev_port='/dev/cu.usbserial-FT677TKA'
# q = Qontroller(serial_port_name=dev_port)




all_pass = True

def expected(cmd):

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
    expected = q.issue_binary_command(cmd.idx.code(),
                                      ch=cmd.addr,
                                      **args)

    return expected


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
    expected = q.issue_binary_command(cmd.idx.code(),
                                      ch=cmd.addr,
                                      **args)

    print(f'{cmd.binary() == expected} {expected} | {cmd.binary()}')

    all_pass =  cmd.binary() == expected
        
    
    return cmd.binary() == expected


def test_binary():
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

        for i in range(255):
            compare(Command(GET, cmd, i))
            compare(Command(SET, cmd, i, data=randint(0, 1000)))
            compare(Command(SET, cmd, i, data=[randint(0, 1000) for _ in range(255)],
                            header={DEXT}))
        
            compare(Command(GET, cmd, i, addr_id=i,
                            header={ADDM}))
        
            compare(Command(GET, cmd, i, addr_id=randint(0, 255),
                            header={ADDM}))

            compare(Command(SET, cmd, i, data=randint(0, 1000),
                            addr_id=i,
                            header={ADDM}))

            compare(Command(SET, cmd, i, data=[randint(0, 1000) for _ in range(255)],
                            addr_id=i,
                            header={ADDM, DEXT}))


            compare(Command(GET, V, i, addr_id=5, header={ADDM}))
    
    print(f'all_pass = {all_pass}')


def test():
    q.issue_binary_command(V.value, ch=0)

def test2():
     c.binary()


def perf_test():
    t =  timeit.timeit('test()', setup='from __main__ import test')
    t2 =  timeit.timeit('test2()', setup='from __main__ import test2')

    print(t)
    print(t2)



if __name__ == '__main__':
    #test_binary()
    # v = 3.01
    # d = math.floor(v * (2**16 / 12))
    # c = Command(SET, V, 1, data=d, header={ALLCH})
    # exp = expected(c)
    # print(exp)
    # print(c.binary())
    # res = q.send_binary(c) 
    # print(res)

    # res = q.send_binary(Command(GET, V, header={ALLCH}))
    # print(res)


    # c = Command(GET, VIP, 0)

    
    # if c.allowed():
    #     res = q.send_binary(c)
    #     print(res)
    # else:
    #     print('Command not allowed')
        

    for cmd in Index:
        if READ in cmd.header_modes():
            res = q.send_binary(Command(GET, cmd, 0))
            print(f'{cmd}  {res}')


        if READ_ALLCH in cmd.header_modes():
            res = q.send_binary(Command(GET, cmd, header={ALLCH}))
            print(f'{cmd}_ALL  {res}')


        

    # q.print_log()
    # p = ProgramGenerator("Binary Program", q.log)
    # p.write('binary_test.json')
