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


q.measure_current_step()

"""
User can use measure_current_step() function to see the 'current step' of every channel

!!! But it will take a considerable time to finish, exact time depends on the total number of channels
!!! If you want to save time, please pass parameters to this function to do a custom test
"""
plt.show()

# In[5]:


q.measure_current_step (min_value = 0, max_value = 8, test_points = 101, test_channel = 0, custom_test = True)

"""
User can do a custom test for a specific channel to save time

min_value and max_value:    will decide the voltage range for the test
test_points:                affects the precision
test_channel:               channel that user tests
custom_test:                set to 'True' if you need to do a custom test, defult value is 'False'
"""
plt.show()

# In[6]:


q.remove_current_step()

"""
Using it to remove the 'current step'
This function will measure the 'current step' and where it happens, then put data into 2 txt files (current_step.txt and voltages.txt)

!!! It will first ask you 'Do you want to import data?'. If you run this function before, you may want to import data rather than do the measurement again.
!!! If you type 'n' (can be any key except 'Y' or 'y'), the it will ask 'Do you want to measure the current step for all channels?'. Type 'Y' or 'y' to do it.
!!! If you type 'n' twice for the pervious questions, you will quit and disable this 'remove_current_step()' function
"""
plt.show()

# In[8]:


q.measure_current_step (min_value = 0, max_value = 8, test_points = 101, test_channel = 0, custom_test = True)

"""
Now, if we run this 'measure_current_step()' function again, we can see the 'current step' is removed
"""
plt.show()

# In[10]:


q.measure_current_step (min_value = 2, max_value = 3, test_points = 201, test_channel = 0, custom_test = True)

"""
However, if we try to use small voltage step in the test, there will be a spike rather than step, which we saw in the pervious test
"""
plt.show()

# In[12]:


q.remove_current_step(adjustment_value = 0.03)

"""
If you want, you can pass this 'adjustment_value' to remove the spike.
Because the amplifier create a floating voltage around ~0.05V, so 'current step' can not be remove completely. Therefore, a spike is left

!!! This adjustment_value has a defult value of 0.01
!!! To change this value, just run this 'remove_current_step()' again, and type 'y' for the first question, no need for measuring the current step again.
"""


# In[13]:


q.measure_current_step (min_value = 2, max_value = 3, test_points = 201, test_channel = 0, custom_test = True)

plt.show()
# In[55]:


q.close()


# In[ ]:




