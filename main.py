"""
AUTHOR: KASHFIA (ASH) MAHMOOD
DATE: 06/14/2023
ACKNOWLEDGEMENTS: John Allen Indergaard for his sacrifices & Matt for his GUI praise
"""

import GUI
import ni
import motor
import stm



# function: start_app
# purpose: begins application and sets darkmode settings
# parameters: none
# return: none
def start_app():
    GUI.begin()
    # we only get to this point once gui closes
    # when closed properly via x settings, reset all components that may have been on
    #ni.ni_set('vacuum', False)
    ni.ni_set('heater', True)
    ni.ni_set('heater_controller', True)
    ni.ni_set('A_motor_power', True)
    ni.ni_set('light', False)
    ni.ni_set('stm_rst', True)
    ni.ni_set('actuator_trig', True)

    #motor.close() #modified to test by gary


# main func
if __name__ == '__main__':
    x = motor.init()
    #stm.reset()  # reset stm
    if x[0] == 0 or x[1] == 0 or x[2] == 0 or x[3] == 0 or x[4] == 0:  # check for initialization failures
        print("Setup failed. Exiting program.")
        motor.close()
    else:
        print("Starting application...")
        start_app()
        # only get here if app is closed gracefully (right click)
        ni.ni_set('A_motor_power', False)
        motor.close()
        GUI.closeGUI()

