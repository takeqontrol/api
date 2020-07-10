import qontrol
import sys

# Setup Qontroller
# serial_port_name = "/dev/tty.usbserial-FT31EUVZ"
serial_port_name = "COM5"
q = qontrol.QXOutput(serial_port_name = serial_port_name, response_timeout = 0.1)

print ("Qontroller '{:}' initialised with firmware {:} and {:} channels".format(q.device_id, q.firmware, q.n_chs) )



print("\n\n WARNING!!! \n\n This example will cause non-zero voltages to be set on the driver outputs. \n Do not proceed if a sensitive device is connected.\n\n")
print("Would you like to proceed? (y/n)")

value_in = input()

if (value_in.upper() == "Y"):

	# Set voltage on each channel to its index in volts mod 8, read voltage, current
	for channel in range(q.n_chs):
		
		# Voltage should be set to index modulo 8 (e.g. ch 11 -> 3V)
		set_voltage = channel % 8
		
		# Set voltage
		q.v[channel] = set_voltage
		
		# Measure voltage
		measured_voltage = q.v[channel]
		
		# Measure current
		measured_current = q.i[channel]
		
		print ("Channel {:} set to {:} V, measured {:} V and {:} mA".format(channel, set_voltage, measured_voltage, measured_current) )


	# Set all channels to zero
	q.v[:] = 0

	q.close()
else:
	q.close()
	sys.exit("Example complete.")

	

