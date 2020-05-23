
Getting Started Guide
---------------------

This Getting started document will guide you through the first configuration and test of the q8 unit
attached to a Qontrol motherboard. 

This guide requires :

- a computer connected to the internet to let the system download the serial port USB drivers 

- (optionally) a program for serial port communication (e.g. Teraterm for windows, CoolTerm for Mac Osx, Linux)



Connection of the unit
######################




.. |Q8iVStilImg| image:: Images/Q8iv_stil.jpg
  :width: 75
  :alt: UQ8iv picture of the device

.. |BackPlaneImg| image:: Images/BP8-top.jpg
  :width: 100
  :alt: BP8-top motherboard image



This procedure is valid for both the Q8 and the Q8iv products. 




* Insert the Q8iv (or any other compatible control unit) in one of the backplanes/motherboards (e.g. BP8): 

  
  |Q8iVStilImg| |BackPlaneImg| 

* Connect the backplane (motherboard) unit to the computer using a cable/adapter with a USB mini b female plug at one of the two ends, like the one shown below:


  .. image:: Images/usbminib.jpg
    :width: 100
    :alt: USB mini b cable adapter


* Power the unit, using a compatible power supply (e.g. PS15KIT):

  .. image:: Images/PS15KIT.jpg
    :width: 100
    :alt: USB mini b cable adapter

* Al the side LEDs in the units should progressively turn on and off again leaving only the bottom green LEDs on, while the units are in idle. 


Configuration of the serial communication
#########################################

Controlling the unit using a serial communication software
**********************************************************
 Serial communication software in any operating system (OS) can be used to control the units, some examples: 

 - Teraterm (Windows)
 - CoolTerm (Mac) 
 - Terminal/Command line (Linux)


**General Configuration settings.**

*Serial parameters*:

- 8 bits for Data 
- 1 bit for stop 
- no parity check 
- no flow control
- Baud Rate 115200

**Teraterm Configuration** 

**Mac CoolTerm Configuration**
To check the name of the device

ls /dev/tty.usb*



**Linux Command Line**

http://my.fit.edu/~msilaghi/ROB/iCreate/serial.pdf


To check the name of the device

ls /dev/tty.usb*



First operations and tests
##############################

First Troubleshouting 
#####################





Notes and disclaimer
#####################



If you find an error in this document, or have suggestions for how we could make it better, please do get in touch with us at support@qontrol.co.uk with your comments.

The information provided in this document is believed to be accurate at the time of publication. It is provided for information only, ‘as is’, and without guarantee of any kind. 

Qontrol Systems LLP, its subsidiaries and associates accept no liability for damage to equipment, hardware, or the customer application, or for labour costs incurred due to the information contained in this document.