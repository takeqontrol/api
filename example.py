import qontrol
import sys

# Setup Qontroller
# serial_port_name = "/dev/tty.usbserial-FT31EUVZ"
serial_port_name = "COM5"
q = qontrol.QXOutput(serial_port_name = serial_port_name, response_timeout = 0.1)

print ("Qontroller '{:}' initialised with firmware {:} and {:} channels".format(q.device_id, q.firmware, q.n_chs) )



print("\n\n WARNING!!! \n\n This test is going to set voltages on the driver different from 0 V. \n Please disconnect any sensitive Hardware from controller.\n\n")
print("type y if you agree in setting voltages to values different thatn 0 V:")

value_in = input()

print(value_in)
if (value_in == "n") or (value_in == "N"):
	q.close()
	sys.exit("You have chosen not to set the voltage. Exiting test.")
elif (value_in == "y") or (value_in == "Y"):
	# Set voltage on each channel to its index in volts, read voltage, current
	for channel in range(q.n_chs):
		set_voltage = channel
		# Set voltage
		q.v[channel] = set_voltage
		# Measure voltage (Q8iv)
		measured_voltage = q.v[channel]
		# Measure current (Q8iv, Q8b, Q8)
		measured_current = q.i[channel]
		print ("Channel {:} set to {:} V, measured {:} V and {:} mA".format(channel, set_voltage, measured_voltage, measured_current) )


	# Set all channels to zero
	q.v[:] = 0

	q.close()
else:
	q.close()
	sys.exit("Invalid input. Admitted values: y or n Exiting test.")

	

