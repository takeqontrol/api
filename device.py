import qontrol
import serial
import serial.tools.list_ports
from virtual_module import VirtualModule
from gen_program import *
from pprint import pprint

N_CH = 8
dev_port='/dev/tty.usbserial-FT3Z4WXD'





vm = VirtualModule()
q = qontrol.Qontroller(serial_port_name=dev_port)


pc = ProgramGenerator(q)

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


pc.write_prog('test.json')

