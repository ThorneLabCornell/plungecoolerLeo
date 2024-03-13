"""
AUTHOR: KASHFIA (ASH) MAHMOOD
DATE: 06/14/2023
ACKNOWLEDGEMENTS: John Allen Indergaard for his sacrifices & Matt for his GUI praise
"""

import globals
import GUI
import ni
#import motor

import os
import sys
import time
from timeit import default_timer as timer
import logging

# global data collection
current_probe_temp = 0



# function: start_app
# purpose: begins application and sets darkmode settings
# parameters: none
# return: none
def start_app():
    GUI.begin()
    # we only get to this point once gui closes
    # when closed properly via x settings, reset all components that may have been on
    # ni.ni_set('vacuum', True)
    # ni.ni_set('heater', True)
    # ni.ni_set('heater_controller', False)
    # ni.ni_set('A_motor_power', True)
    # ni.ni_set('light', False)
    # ni.ni_set('stm_rst', True)



# main func
if __name__ == '__main__':
        print("Starting application...")
        start_app()
        # only get here if app is closed
        motor.close()
        GUI.closeGUI()
        # ni.drop_dispense()

