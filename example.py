import qontrol

# Setup Qontroller
serial_port_name = "/dev/tty.usbserial-FT06QAZ5"
q = qontrol.QXOutput(serial_port_name = serial_port_name, response_timeout = 0.1)

print ("Qontroller '{:}' initialised with firmware {:} and {:} channels".format(q.device_id, q.firmware, q.n_chs) )


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