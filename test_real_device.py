from qontrol import *
import ref_qontrol
from copy import deepcopy
from pprint import pprint
from virtual_module import *
import time
import pytest
import math

def ref_binary(q, cmd):
    args = {}
    for i in Header:
        if i == BIN:
            continue
        
        if i in cmd.header:
            args[str(i.name)] = 1
        else:
            args[str(i.name)] = 0


    if DEXT in cmd.header:
        data = map(cmd.binary_data_conv, cmd.data)
    else:
        data = cmd.binary_data_conv(cmd.data)
            
    args['value_int'] = data if data is not None else 0
    
    args['addr_id_num'] = cmd.addr_id
    expected = q.issue_binary_command(cmd.idx.code(),
                                      ch=cmd.addr,
                                      **args)

    if (cmd.idx == V or cmd.idx == I) and RW in cmd.header:
        expected = list(map(lambda x: float(x[0].split(' ')[0]), expected))

    if cmd.idx == LIFETIME:
        expected = int(expected[0][0].split(' ')[0])

    return expected


do_not_write =  {SAFE, ICAL, VCAL, IMAX, VMAX, ROCOM, OK, ADCN, ADCT, CCFN, LED, NVM, NUP}


def cmds_supporting(header_mode, exclude=None):
    exclude = [] if exclude is None else exclude
    return [c for c in CmdIndex if c.supports(header_mode) and c not in exclude]

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


def gen_commands(n_ch):
    cmds = []
    for c in cmds_supporting(READ, exclude={LOG, NVM}):
        for ch in range(n_ch):
            cmds.append(Command(c, addr=ch))

    for c in cmds_supporting(READ_ALLCH, exclude={LOG, NVM}):
        cmds.append(Command(c, header=ALLCH))

    # for c in cmds_supporting(WRITE, exclude=do_not_write):
    #     for ch in range(n_ch):
    #         data, conv = random_data_for_cmd(c)
    #         cmds.append(Command(c, addr=ch, data=data,
    #                     binary_data_conv=conv))
    # for c in [V]:
    #     for ch in range(n_ch):
    #         data, conv = random_data_for_cmd(c, ret_list=True,
    #                                          max_data_size=n_ch-ch)
            
    #         cmd = Command(c, addr=ch, data=data, binary_data_conv=conv, header=DEXT)
    #         cmds.append(cmd)

    return cmds



def cmd_set_test(cmds, test_f, exp_f):
    q = Qontroller(device_id='Q8iv-0001', response_timeout=0.1, log_max_len=None)

    compare = []
    res = []
    for cmd in cmds:
        result = test_f(q, cmd)

        if (cmd.idx == V or cmd.idx == I) and RW in cmd.header:
            result = list(map(lambda x: float(x[0].split(' ')[0]), result))
            comp = lambda r, e: all(map(lambda e: math.isclose(e[0], e[1], rel_tol=0.01,
                                        abs_tol=0.01), zip(r, e)))
            
        else:
            comp = lambda r, e: r == e


        if cmd.idx == LIFETIME:
            result = int(result[0][0].split(' ')[0])
            comp = lambda r, e: math.isclose(r, e, rel_tol=0.05)
        
        compare.append(comp)    
        res.append(result)
        

    # log = deepcopy(q.log)
    # q.close()

    # time.sleep(1)
    refq = ref_qontrol.Qontroller(device_id='Q8iv-0001', response_timeout=0.1)

    exp = []
    for cmd in cmds:
        exp_res = exp_f(refq, cmd)
        exp.append(exp_res)

    # ref_log = deepcopy(refq.log)
    # refq.close()

    return (res, exp, compare)


# pprint(gen_commands(16), indent=4)



@pytest.mark.parametrize('cmd', gen_commands(32))
def test_cmd(cmd):
    res, exp, compare = cmd_set_test([cmd],
        test_f=lambda q, cmd: q.send_binary(cmd),
        exp_f=lambda q, cmd: ref_binary(q, cmd))

    for r, e, comp in zip(res, exp, compare):
        result =  comp(r, e)
        print(r, e)
        print(result)
        assert result

# cmds = [Cmd(V, header=ALLCH), Cmd(I, header=ALLCH), Cmd(ID, header=ALLCH)]

# log, ref_log, res, exp, compare = test_cmd_set(cmds, test_f=lambda q, cmd: q.send_binary(cmd),
#                                                      exp_f=lambda q, cmd: ref_binary(q, cmd))


# for r, e, comp in zip(res, exp, compare):
#     print('----')
#     print(r)
#     print(e)
#     print(comp(r, e))
    
    

# pg = ProgramGenerator()


# l1 = pg._parse_log(log)
# l2 = pg._parse_log(ref_log)


# with open("log.txt", "w") as log_file:
#     pprint(l1, log_file, indent=2)

# with open("ref_log.txt", "w") as log_file:
#     pprint(l2, log_file, indent=2)    
c = Command(I, addr=13)
pprint(c, indent=4)
test_cmd(c)
