#!/usr/bin/env python
# coding: utf-8

# In[1]:


import time
import matplotlib.pyplot as plt
import qontrol_dev


# In[2]:


"""
This example will show how to remove the 'current step' by using remove_current_step function.
It is worth noting that the current step is caused by hardware (amplifier), and it does not affect the actual set current value, only the measurement result.
So this is a fix at the software level.
"""


# In[3]:


q = qontrol_dev.QXOutput(serial_port_name = "COM3")
print ("Qontroller '{:}' initialised with firmware {:} and {:} channels".format(q.device_id, q.firmware, q.n_chs) )

q.v[:] = 0


# In[4]:


q.measure_current_step (min_value = 0, max_value = 8, test_points = 101, test_channel = 0, custom_test = True)

"""
There is a current step in the VI curve
"""
plt.show()

# In[5]:


q.remove_current_step()

"""
Using it to remove the 'current step'
This function will measure the 'current step' and where it happens, then put data into 2 txt files (current_step.txt and voltages.txt)

!!! It will first ask you 'Do you want to import data?'. If you run this function before, you may want to import data rather than do the measurement again.
!!! If you type 'n' (can be any key except 'Y' or 'y'), the it will ask 'Do you want to measure the current step for all channels?'. Type 'Y' or 'y' to do it.
!!! If you type 'n' twice for the pervious questions, you will quit and disable this 'remove_current_step()' function
"""
plt.show()

# In[6]:


q.measure_current_step (min_value = 0, max_value = 8, test_points = 101, test_channel = 0, custom_test = True)

"""
The current step is removed
"""
plt.show()

# In[ ]:




