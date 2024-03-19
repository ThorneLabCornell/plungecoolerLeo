import globals as globs
import time
from timeit import default_timer as timer
import ni
import threading
import motor
import ni
from ctypes import *
# Load library
# EPOS Library Path for commands - modify this if moving to a new computer
path = 'C:\\Program Files (x86)\\maxon motor ag\\EPOS IDX\\EPOS2\\04 Programming\\Windows DLL\\LabVIEW\\maxon EPOS\\Resources\EposCmd64.dll'
cdll.LoadLibrary(path)
epos = CDLL(path)


# function: nudgeBegin
# purpose: initializes the device to receive nudge inputs via the buttons & disables plunge functionality
# parameters: self
# return: none
def Dispenser_start_func(self):
    ni.ni_set('Dispenser_en', False) #set enable signal to low to allow motor movement
    # ni_set('light', True)  # turn on light to indicate movement stage
    # disable plunge, home, startNudge buttons, enable control buttons and stop nudge buttons in GUI (figured out by Gary after 3hrs:))
    #globs.gui.Dispenser_home.setEnabled(True)
    globs.gui.upNudge.setEnabled(True)
    globs.gui.stopButton.setEnabled(True)
    globs.gui.downNudge.setEnabled(True)
    globs.gui.startNudge.setEnabled(False)
    print("start")


# function: Dispenser_up_func
# purpose: nudges the carriage up
# parameters: self
# return: none
def Dispenser_up_func():
    print("test")
    new_pos = globs.Dispenser_position - int(globs.gui.nudge_spinbox.value()) #A_spinbox.value() is what user inputs in GUI
    Dispenser_move(globs.A_UP, int(globs.gui.nudge_spinbox.value()))#A_UP is TRUE
    globs.gui.current_pos_label.setText(str(new_pos))  # update position label in GUI


# function: Dispenser_stop_func
# purpose: stops nudge function
# parameters: self
# return: none
def Dispenser_stop_func(self):
    ni.ni_set('Dispenser_en', True)#set enable signal to high to stop motor movement
    #disable control buttons and stop nudge buttons in GUI
    globs.gui.upNudge.setEnabled(False)
    globs.gui.stopButton.setEnabled(False)
    globs.gui.downNudge.setEnabled(False)
    globs.gui.startNudge.setEnabled(True)


# function: downNudgeFunc
# purpose: nudges the carriage down
# parameters: self
# return: none
def Dispenser_down_func():
    new_pos = globs.Dispenser_position + int(globs.gui.nudge_spinbox.value())
    Dispenser_move(globs.A_DOWN, int(globs.gui.nudge_spinbox.value()))
    globs.gui.current_pos_label.setText(str(new_pos))  # update position label


def Dispenser_move_to_func(self):
    to_pos = int(globs.gui.Dispenser_spinbox_2.value())
    direction = globs.A_UP if to_pos > globs.Dispenser_position else globs.A_DOWN
    amount = abs(globs.Dispenser_position - to_pos)
    Dispenser_move(direction, amount)


def Dispenser_move(direc, steps):
    #direction algorithm
    if direc == globs.A_UP:
        globs.Dispenser_position -= steps
    else:
        globs.Dispenser_position += steps
    moveT = threading.Thread(target=ni.Dispenser_move_thread, args=(direc, steps))
    moveT.start()#invokes A.movethread to be ran in parallel to current program (taking in inputs of direc and steps)

def Dispense_Plunge():
    # ni.drop_dispense()
    # Dispense_start = timer()
    # while True:  # hold loop until time is reached, then plunge
    #     if timer() - Dispense_start >= globs.dispenser_delay:
    #         break
    # if globs.gui.actuator.isChecked():
    #     globs.dispenser_delay+=0.49#delay by another 50ms
    #     ni.pneumatic_actuator_push()
    #     while True:  # hold loop until time is reached, then plunge
    #         if timer() - Dispense_start >= globs.dispenser_delay:
    #             break
    vacTimer = timer()
    print("pressseeed dispense and plunge")
    print(abs(motor.get_position()))
    if abs(motor.get_position()) > 75: # outside bounds of normal plunge condition, not homere properly
        print("incorrect homing")
        return
    print("forward")
    # resert global tracking variables
    globs.plungeData.clear()  # clear any previously collected data
    globs.plungeTime.clear()
    globs.plungePosData.clear()
    globs.plungeVelData=[]
    globs.plungeTemp.clear()
    globs.plunge_temp_time.clear()
    pptimer = timer()
    globs.gui.graphVel.clear()  # clear graph widget
    globs.gui.graphVelPos.clear()
    globs.gui.graphTempPos.clear()

    globs.gui.graphTempPos.setTitle("Plunge Cooler Temperature vs Time", color="w", size="10pt")
    styles = {"color": "white", "font-size": "10px"}
    globs.gui.graphTempPos.setLabel("left", "Voltage (V)", **styles)
    globs.gui.graphTempPos.setLabel("bottom", "Time (s)", **styles)
    print(globs.gui.plungepause.isChecked())
    vac_time=globs.gui.vac_on_time.value()
    if globs.gui.plungepause.isChecked():
        epos.VCS_SetEnableState(motor.keyHandle, motor.nodeID, byref(motor.pErrorCode))  # enable device
        pp_wait_time = globs.gui.pp_time_box.value() #substrate by deposition time
        # TODO: characterize how much extra t delay there is at beginning of PPP. might not be a huge deal
        if globs.gui.plungevac.isChecked() and vac_time > pp_wait_time:
            globs.gui.vac_on_time.setEnabled(False)
            globs.gui.plungevac.setEnabled(False)  # any conflicting settings are off or set settings are kept constant
            start = timer()
            ni.ni_set('vacuum', False)  # turn on vacuum
            while True:  # hold loop until time is reached, then plunge
                if timer() - start >= vac_time - pp_wait_time -globs.dispenser_delay:
                    break
            globs.gui.vac_on_time.setEnabled(True)  # return previous settings to enable changes
            globs.gui.plungevac.setEnabled(True)

        #motor.move_nudge('down', globs.gui.plungepausedist.value())  # move to the distance

        if globs.gui.plungevac.isChecked() and vac_time == pp_wait_time:
            ni.ni_set('vacuum', False)
        Dispense_start = timer()  # start timer for plunge pause plunge

        ni.drop_dispense()
        while True:  # hold loop until time is reached, then plunge
            if timer() - Dispense_start >= globs.dispenser_delay:
                break
        if globs.gui.actuator.isChecked():
            Actuate_start = timer()  # start timer for plunge pause plunge
            ni.pneumatic_actuator_push()
            while True:  # hold loop until time is reached, then plunge
                if timer() - Actuate_start >= globs.actuator_delay:
                    break

        vac_on = False
        pptimer = timer()
        while True:  # hold in loop until pause time has been reached, then proceed to plunging stage
            if globs.gui.plungevac.isChecked() and ~vac_on and vac_time < pp_wait_time and (
                    timer() - pptimer > vac_time):
                ni.ni_set('vacuum', False)
                vac_on = True
            if timer() - pptimer > pp_wait_time:
                break
        motor.move_plunge()  # arbitrary amount to ensure fault state reached; -ve is down
        ni.ni_set('vacuum', True) #turn off vacuum

    elif globs.gui.plungevac.isChecked():  # vacuum time; note that this does not add to the p-p-p time
        globs.gui.vac_on_time.setEnabled(False)
        globs.gui.plungevac.setEnabled(False)  # any conflicting settings are off or set settings are kept constant
        wait_time = globs.gui.vac_on_time.value()  # read time to wait; turns on vacuum and pauses before plunge
        start = timer()
        ni.ni_set('vacuum', False)  # turn on vacuum
        while True:  # hold loop until time is reached, then plunge
            if timer() - start >= wait_time or timer() - pptimer >= wait_time:
                Dispense_start = timer()  # start timer for plunge pause plunge
                ni.drop_dispense()
                while True:  # hold loop until time is reached, then plunge
                    if timer() - Dispense_start >= globs.dispenser_delay:
                        break
                if globs.gui.actuator.isChecked():
                    Actuate_start = timer()  # start timer for plunge pause plunge
                    ni.pneumatic_actuator_push()
                    while True:  # hold loop until time is reached, then plunge
                        if timer() - Actuate_start >= globs.actuator_delay:
                            break
                epos.VCS_SetEnableState(motor.keyHandle, motor.nodeID, byref(motor.pErrorCode))  # disable device
                motor.move_plunge()  # arbitrary amount to ensure fault state reached; -ve is down
                break
        ni.ni_set('vacuum', True)  # turn off vacuum following plunge
        globs.gui.vac_on_time.setEnabled(True)  # return previous settings to enable changes
        globs.gui.plungevac.setEnabled(True)

    else:  # if no vacuum is on, just plunge through; also enables plunge timer func
        global temp_timer
        temp_timer = timer()
        tempcollect = timer()
        # print('ran')

        # remove the below to stop it from collecting time; this is a temporary feature!
        # while timer() - tempcollect < 0.5:  # read initial temperature for 1s
        #     plungeTemp.append(read_temperature())
        #     plunge_temp_time.append(timer() - temp_timer)
        ni.drop_dispense()
        Dispense_start = timer()
        while True:  # hold loop until time is reached, then plunge
            if timer() - Dispense_start >= globs.dispenser_delay:
                break
        if globs.gui.actuator.isChecked():
            globs.dispenser_delay += 0.49  # delay by another 50ms
            ni.pneumatic_actuator_push()
            while True:  # hold loop until time is reached, then plunge
                if timer() - Dispense_start >= globs.dispenser_delay:
                    break
        epos.VCS_SetEnableState(motor.keyHandle, motor.nodeID, byref(motor.pErrorCode))  # disable device
        motor.move_plunge()  # arbitrary amount to ensure fault state reached; -ve is down

    tempcollect = timer()
    # while timer() - tempcollect < 1: # read concluding temperature for 1s
    #     plungeTemp.append(read_temperature())
    #     plunge_temp_time.append(timer() - temp_timer)

    globs.gui.graphTempPos.plot(globs.plunge_temp_time, globs.plungeTemp)  # this will repost the data after plunge

    value_n = (-1 * (motor.get_position()-globs.pos_home_raw) * globs.leadscrew_inc / globs.encoder_pulse_num)  # approximate updated position
    globs.gui.current_pos_label.setText(str(value_n))  # update label with position
    globs.gui.graphVel.plot(globs.plungeTime, [pos * (globs.leadscrew_inc / globs.encoder_pulse_num) for pos in globs.plungePosData])  # plot collected data
    globs.gui.graphVelPos.plot([pos * (globs.leadscrew_inc / globs.encoder_pulse_num) for pos in globs.plungePosData], [vel * (globs.leadscrew_inc / globs.encoder_pulse_num) for vel in globs.plungeVelData])  # plot vel vs pos -- seet to plungePosData vs plungeData v vs pos