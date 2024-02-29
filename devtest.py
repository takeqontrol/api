from qontrol import *
from virtual_module import *
from pprint import pprint
import time
from collections import deque

# q = Qontroller(device_id='Q8iv-0001', response_timeout=0.400, log_max_len=None)


# do_not_write =  {SAFE, ICAL, VCAL, IMAX, VMAX, ROCOM, OK, ADCN, ADCT, CCFN, LED, NVM}

# for c in [V, I]:

#     if c.supports(READ_ALLCH):
#         cmd = Command(c, header=ALLCH)
            
#         q.send_binary(cmd)
#         time.sleep(0.01)
            
#         q.send_ascii(cmd)
#         time.sleep(0.01)


    # if c.supports(READ_ALLCH):
    #     for ch in range(16):
    #         cmd = Command(c, header=ALLCH)
            
    #         q.send_binary(cmd)
    #         time.sleep(0.01)
            
    #         q.send_ascii(cmd)
    #         time.sleep(0.01)
        
    # if c.supports(WRITE) and c not in do_not_write:
    #     for ch in range(16):
    #         cmd = Command(c, addr=ch, data=1)

    #         q.send_binary(cmd)
    #         time.sleep(0.01)
            
    #         q.send_ascii(cmd)
    #         time.sleep(0.01)
        





# pg = ProgramGenerator('Two Q8iv', q.log)
# pg.write('progs/two_q8iv_3.json')



c = CustomHandler()

@c.register
def handle_unknown_command(cmd, cnt, vm):
    vm._queue_out(f'Unknown command: {cmd}')

p = Program.from_json_file('progs/two_q8iv_3.json', custom=c)
vm = VirtualModule(program=p)
q = Qontroller(virtual_port=vm.port, response_timeout=0.400)


res = q.send_binary(Cmd(ICAL, header=ALLCH))
print(res)
