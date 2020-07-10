

import qontrol
import time, sys, random

serial_port_name = "/dev/tty.usbserial-FT3JOAAG"
q = qontrol.MXMotor(serial_port_name = serial_port_name)


sys.stdout.write ("\nQontroller '{:}' initialised with firmware {:} and {:} channels\n".format(q.device_id, q.firmware, q.n_chs) )

sys.stdout.write ("\nWaiting 10s\n")
time.sleep(10.0)

chs = [0,1]


# Set microsteps (7 -> 128 usteps)
q.ustep[:] = 7
for i in range(20):

	print ("iteration ",i)
	
	# Go
	for ch in chs:
		v = random.uniform(100.0,300.0)
		if (v < 200):
			q.ustep[ch] = 8
		else:
			q.ustep[ch] = 7
		q.vmax[ch] = v
		q.x[ch] = random.uniform(0,3000);

	# Wait for motion to stop
	time.sleep(0.1)
	q.wait_until_stopped()


# Go back
q.ustep[:] = 8
q.vmax[:] = 200.0
q.x[:] = 0;

# Wait for motion to stop
sys.stdout.write ("Waiting for motion to stop...")
sys.stdout.flush()
q.wait_until_stopped()
sys.stdout.write ("stopped.\n")