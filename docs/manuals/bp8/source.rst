The BP8 is a backplane which can host up to eight Qontrol modules, providing power, serial communications, and providing a shielded analog output. Up to 64 analog channels are presented to a shielded connector compatible with the `CAB8 <https://qontrol.co.uk/product/cab8>`_ cable.

.. pdf-include:: ../../_static/manuals/bp8/img/hero3.pdf
    :toolbar: 0

Description
===========

The BP8 provides wiring and connectors to facilitate the connection of the 64 input/output channels of eight Qontrol modules to a single shielded CAB8 cable. It receives power for the connected modules and provides USB-to-RS232 conversion to enable communication with the PC. It also includes CABCHN connectors for linking multiple Qontrol backplanes together.


Power
-----

Four power receptacles are provided:

1. Barrel for 5-V digital supply[#dig]_ (optional)
2. Barrel for analog supply
3. Test (banana) connector for positive analog supply terminal (red or yellow)
4. Test connector for negative analog supply terminal (black)

**Warning**: When using the barrel connectors, take care to insert the correct supply into the each connector. Exceeding 5.5 V on the digital supply may damage or destroy all connected modules.

The ratings of each power interface are listed below. The barrel connectors can be used to conveniently supply low-current applications, while the test (banana) connections should be used for more demanding applications. 4-mm test connectors are compatible with most benchtop power supplies.


.. table:: Barrel connector properties

 +------------------+-------------------+
 | Maximum current	| 5 A				|
 +------------------+-------------------+
 | Barrel diameter	| 6.3 mm			|
 +------------------+-------------------+
 | Pin diameter		| 2.1 mm & 2.5 mm	|
 +------------------+-------------------+
 | Polarity			| Centre positive	|
 +------------------+-------------------+


.. table:: Test connector properties

 +------------------+-------------------+
 | Maximum current	| 24 A				|
 +------------------+-------------------+
 | Pin diameter		| 4 mm				|
 +------------------+-------------------+


.. [#dig] Only the following modules use the digital supply: Q8iv, Q8b.


CAB8 parallel connection
------------------------

The `CAB8 <https://qontrol.co.uk/product/cab8>`_ cable provides a shielded parallel connection for 64 analog signals. It comprises 68 conductors, with four conductors reserved. If designing a custom interposer for your own application, leave these four pins floating. A pinout diagram of the CAB8 connector (BP8 side) is shown below.

.. pdf-include::  ../../_static/manuals/bp8/img/cab8.pdf
    :toolbar: 0

Communications
--------------

A standard mini-USB port is provided to communicate with the modules in the backplane. This port converts to and from the internal RS-232 bus using genuine FTDI parts[#ftdi]_. Communicate with the first module by using these virtual COM port settings:

 ==================	===========	
 Baud rate			115200
 Bits per symbol	8
 Stop bits			1
 Flow control		None
 ==================	===========
 
Test the connection with a universal command like "``ID?``". For more information on the communications protocol of each module, consult that module's documentation.

.. [#ftdi] Drivers for all major operating systems can be found online at `ftdichip.com/drivers/vcp-drivers/ <https://ftdichip.com/drivers/vcp-drivers/>`_.

Chain interface
---------------

The chain interface allows the user to connect multiple backplanes together to make communications and power distribution easy. Qontrol offers the `CABCHN cable <https://qontrol.co.uk/product/cabchn>`_ to join two backplanes, such as the BP8, together at the input and output CABCHN ports. A pinout of the input and output ports is shown below.

**Warning**: When chaining multiple backplanes together, pay attention to the maximum current handling limits of the power connectors in the chain, particularly the first one.

.. pdf-include::  ../../_static/manuals/bp8/img/cabchn.pdf
    :toolbar: 0

Indicator LED
-------------

The BP8 includes a bi-colour LED indicator. This backplane indicator is simply an ``OR`` of the "device active" (green) and "error" (red) indicator signals of any connected modules—no logic is done on the backplane itself.


Populating the backplane
========================

Insert the first module into Slot 0 of the backplane. The inserted modules must form a *continuous chain* from the first slot, to allow the modules to communicate with each other. If your application calls for some slots to remain empty, Qontrol offers the `BLANK8 <https://qontrol.co.uk/product/blank8>`_ blank module which you can insert instead to achieve this effect.


Mechanical
==========

.. pdf-include::  ../../_static/manuals/bp8/img/mech.pdf
    :toolbar: 0