from qontrol import *
from virtual_module import *
from pprint import pprint
import time
from collections import deque
import random
import math

# q = Qontroller(device_id='Q8iv-0001', response_timeout=0.4, log_max_len=None)


do_not_write =  {SAFE, ICAL, VCAL, IMAX, VMAX, ROCOM, OK, ADCN, ADCT, CCFN, LED, NVM, NUP}


def cmds_supporting(header_mode, exclude=None):
    exclude = [] if exclude is None else exclude
    return [c for c in CmdIndex if c.supports(header_mode) and c not in exclude]


def send_both(cmd, sleep=0.0):
    q.send_binary(cmd)
    time.sleep(sleep)
            
    q.send_ascii(cmd)
    time.sleep(sleep)


def random_data_for_cmd(c, ret_list=False, max_data_size=100):
    data_gen = None
    data_conv = lambda x: x
    match c:
        case CmdIndex.V:
            data_gen = lambda: round(random.uniform(0.0, 12.0), 2)
            data_conv = lambda d: math.floor(d * (2**16 / 12))
            
        case CmdIndex.I:
            data_gen = lambda: round(random.uniform(0.0, 24.0), 2)
            data_conv = lambda d: math.floor(d * (2**16 / 24))

        case CmdIndex.NUP:
            data_gen = lambda: random.randint(0, 16)

    if ret_list:
        data = [data_gen() for _ in range(max_data_size)]
    else:
        data = data_gen()

    return data, data_conv

N_CH = 16

# print('READ')
# for c in cmds_supporting(READ):
#     for ch in range(N_CH):
#         print(f'{c} {ch}')
#         send_both(Command(c, addr=ch))

# print('READ ALLCH')
# for c in cmds_supporting(READ_ALLCH):
#     print(f'{c}')
#     send_both(Command(c, header=ALLCH))

# print('WRITE')
# for c in cmds_supporting(WRITE, exclude=do_not_write):
#     for ch in range(N_CH):
#         data, conv = random_data_for_cmd(c)
#         print(f'{c} {ch} {data}')
#         send_both(Command(c, addr=ch, data=data,
#                   binary_data_conv=conv))
        

# print('WRITE DEXT')
# for c in [V]:
          
#     for ch in range(N_CH):
#         data, conv = random_data_for_cmd(c, ret_list=True,
#                                          max_data_size=N_CH-ch)
#         print(f'{c} {ch} {data}')
#         cmd = Command(c, addr=ch, data=data, binary_data_conv=conv, header=DEXT)
#         #send_both(cmd,sleep=0.4)

#         q.send_ascii(cmd)

# data, conv = random_data_for_cmd(V, ret_list=True, max_data_size=N_CH)


# res = q.send_binary(Command(V, data=0, header=ALLCH))
# print(f'{res}')

# res = q.send_binary(Command(V, header=ALLCH))


# print(f'all v = {res}')

# print(f'setting data = {data}')
# c = Command(V, addr=0, data=data, binary_data_conv=conv, header=DEXT)
# q.send_binary(c)


# res = q.send_binary(Command(V, header=ALLCH))
# print(f'all v = {res}')


# res = q.send_binary(Command(ICAL, header=ALLCH))
# print(f'all v = {res}')

# pg = ProgramGenerator('Two Q8iv', q.log)
# pg.write('progs/two_q8iv_5.json')



c = CustomHandler()

@c.register
def handle_unknown_command(cmd, cnt, vm):
    vm._queue_out(f'Unknown command: {cmd}')

p = Program.from_json_file('progs/two_q8iv_5.json', custom=c)
vm = VirtualModule(program=p)
q = Qontroller(virtual_port=vm.port, response_timeout=0.400)


res = q.send_ascii(Cmd(ICAL, header=ALLCH))
print(res)
