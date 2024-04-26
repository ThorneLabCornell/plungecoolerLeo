import globals as globs
from ctypes import *
import stm
import ni
import time
from timeit import default_timer as timer
import threading
from scipy.signal import savgol_filter

# EPOS Library Path for commands - modify this if moving to a new computer
path = 'C:\\Program Files (x86)\\maxon motor ag\\EPOS IDX\\EPOS2\\04 Programming\\Windows DLL\\LabVIEW\\maxon EPOS\\Resources\EposCmd64.dll'

# Load library
cdll.LoadLibrary(path)
epos = CDLL(path)

# define return variables that are used globally
pErrorCode = c_uint()
pErrorInfo = c_char()
MaxStrSize = c_uint()
pDeviceErrorCode = c_uint()
DigitalInputNb = c_uint()

keyHandle = epos.VCS_OpenDevice(b'EPOS2', b'MAXON SERIAL V2', b'USB', b'USB0', byref(pErrorCode))  # specify EPOS version and interface

# Defining a variable NodeID and configuring connection
nodeID = 1  # set to 2; need to change depending on how the maxon controller is set up (check EPOS Studio)
EPOS_BAUDRATE = 1000000
EPOS_TIMEOUT = 500

# PID tuning
PID_P = 400000
PID_I = 1

# acc/decc for nudging
acceleration = 10000
deceleration = 10000

def init():

    print("Initializing MAXON interface, will exit if failed")

    if int(keyHandle) == 0:
        print("keyHandle failed!")

    # initialize device (MAXON)
    x = initialize_device(keyHandle)

    return x


def enable():
    epos.VCS_SetEnableState(keyHandle, nodeID, byref(pErrorCode))  # disable device


def close():
    close_device(keyHandle)


# function: get_position
# purpose: gets position data from encoder and returns it
# parameters: none
# return: int
def get_position():
    pPositionIs = c_long()
    pErrorCode = c_uint()
    ret = epos.VCS_GetPositionIs(keyHandle, nodeID, byref(pPositionIs), byref(pErrorCode))
    return pPositionIs.value  # motor steps


# function: get_velocity
# purpose: gets velocity and returns value
# parameters: none
# return: int (may be float?)
def get_velocity():
    pVelocityIs = c_long()
    pErrorCode = c_uint()
    ret = epos.VCS_GetVelocityIs(keyHandle, nodeID, byref(pVelocityIs), byref(pErrorCode))
    return pVelocityIs.value  # motor steps


# function: move_plunge
# purpose: plunges the carriage downwards rapidly (can set speed and "position"; set to large -ve if plunging full
# parameters: int, int
# return: none
def move_plunge():
    print("entered move_plunge")
    # message to stm32 to start plunge process
    #epos.VCS_SetEnableState(keyHandle, nodeID, byref(pErrorCode))  # disable device
    stop_position = int(globs.gui.brakeBox.value() + get_position() / 2) # + b/c get_position returns a negative. comepnsates for offset in case of ppp
    print("stop pos:" + str(stop_position))
    timepoint_position = int((globs.a_position - globs.a_offset)/globs.A_STEPS_PER_UM)

    stm.clear_input()  # make sure no ACKs etc. are going to mess up plunge
    msg = '2' + str(stop_position).zfill(6) + str(timepoint_position).zfill(6) + '\r\n'

    #stm.brake_set(True) some changes
    stm.write(bytes(msg, 'utf-8'))

    # Start grabbing temp data if desired
    if globs.readTemp_flag:
        tempT = threading.Thread(target=ni.tempLog)
        tempT.start()
    stm.brake_set(False)  # free brake for plunge start
    # motor start accelerating to target velocity
    epos.VCS_SetVelocityRegulatorGain(keyHandle, nodeID, PID_P, PID_I, byref(pErrorCode))  # PID confio
    epos.VCS_SetMaxAcceleration(keyHandle, nodeID, 4294967295, byref(pErrorCode))
    epos.VCS_ActivateVelocityMode(keyHandle, nodeID, byref(pErrorCode))
    epos.VCS_SetVelocityMust(keyHandle, nodeID, globs.plunge_speed, byref(pErrorCode))

    print("moved")  # debug
    #stm.ser.readline() debug
    stm.wait_for_ack()  # wait until stm says the plunge has reached the bottom (braked)
    print("left")
    epos.VCS_SetQuickStopState(keyHandle, nodeID, byref(pErrorCode)) # stop motor

    print("done plunge")

    stm.receivePlungeData()  # listen for the plunge data the stm sends
    globs.plungeVelData.append(0)
    length=len(globs.plungePosData)-1
    print("pos")
    print(globs.plungePosData)
    print("time")
    print(globs.plungeTime)
    for i in range(1,length):
        globs.plungeVelData.append(((globs.plungePosData[i]-globs.plungePosData[i-1])/(globs.plungeTime[i]-globs.plungeTime[i-1])+(globs.plungePosData[i+1]-globs.plungePosData[i])/(globs.plungeTime[i+1]-globs.plungeTime[i]))/2*10)
    globs.plungeVelData.append((globs.plungePosData[length] - globs.plungePosData[length - 1]) / (globs.plungeTime[length] - globs.plungeTime[length -1])*10)
    print("velocity")
    print(globs.plungeVelData)
    print(len(globs.plungePosData))
    print(len(globs.plungeVelData))
    temp = savgol_filter(globs.plungeVelData,len(globs.plungeVelData), 3)
    globs.plungeVelData=temp
    print("no error")
    # for some reason the stm doesnt listen to the very first command after a plunge
    # TODO: fix this for real instead of a sketchy workaround. i'm at a loss for why this is happening.
    plunge_done_flag = True
    stm.reset()

    if globs.readTemp_flag:  # if measuring temp, reclaim the thread
        tempT.join()


# function: move_nudge
# purpose: nudges the carriage upwards or downwards
# parameters: string, int
# return: none
def move_nudge(direction, nudge_step):
    target_speed = 600
    pCurrent = c_short()
    nudge_step = int(nudge_step / globs.leadscrew_inc * globs.encoder_pulse_num)

    if direction == "down":
        nudge_step *= -1

    nudge_step = nudge_step + get_position()

    # TODO: MAKE SURE IT DOESNT GO OUT OF BOUNDS

    print("at: " + str(get_position()) + "; moving to: " + str(nudge_step))
    epos.VCS_SetEnableState(keyHandle, nodeID, byref(pErrorCode))  # disenable device new line
    epos.VCS_ActivateProfilePositionMode(keyHandle, nodeID, byref(pErrorCode))
    epos.VCS_SetPositionProfile(keyHandle, nodeID, target_speed, acceleration, deceleration, byref(pErrorCode))  # set profile parameters
    epos.VCS_HaltPositionMovement(keyHandle, nodeID, byref(pErrorCode))
    #time.sleep(.1)
    stm.brake_set(False)
    print("passed")
    epos.VCS_MoveToPosition(keyHandle, nodeID, nudge_step, True, True, byref(pErrorCode))  # move to position
    time.sleep(.5)
    # TODO: look at reimplementing this for more accurate nudging
    # while True:
    #    epos.VCS_GetCurrentIs(keyHandle, nodeID, byref(pCurrent), byref(pErrorCode))
    #    print(pCurrent.value)
    #    if pCurrent.value <= 400:  # not mving
    #        break
    stm.brake_set(True)



# function: upNudgeFunc
# purpose: nudges the carriage up
# parameters: self
# return: none
def upNudgeFunc():

    epos.VCS_ActivateProfilePositionMode(keyHandle, nodeID, byref(pErrorCode))
    print("upnudge")
    move_nudge("up", globs.gui.nudge_spinbox.value())  # call function to move by nudge distance

    value_n = (-1 * (get_position()-globs.pos_home_raw) * globs.leadscrew_inc / globs.encoder_pulse_num) + globs.gui.nudge_spinbox.value() # approximate updated position
    globs.gui.current_pos_label.setText(str(value_n))  # update position label


# function: downNudgeFunc
# purpose: nudges the carriage down
# parameters: self
# return: none
def downNudgeFunc():
    epos.VCS_ActivateProfilePositionMode(keyHandle, nodeID, byref(pErrorCode))
    print(int(globs.gui.nudge_spinbox.value() / globs.leadscrew_inc * globs.encoder_pulse_num))
    move_nudge("down", globs.gui.nudge_spinbox.value())  # calculate nudge value from input & move

    value_n = (-1 * (get_position()-globs.pos_home_raw) * globs.leadscrew_inc / globs.encoder_pulse_num) + globs.gui.nudge_spinbox.value()  # approximate updated position

    globs.gui.current_pos_label.setText(str(value_n))  # update position label


def clear_errors():
    p3 = epos.VCS_ClearFault(keyHandle, nodeID, byref(pErrorCode))  # clear all faults
    p5 = epos.VCS_SetEnableState(keyHandle, nodeID, byref(pErrorCode))  # disable device


# function: get_error
# purpose: debugging function that will take maxon error codes and output the HEX reference, which can be referred to
# in the PDF of EPOS commands in debugging prevalent issues - outputs to console
# parameters: string, bool
# return: none
def get_error(task, bool_status):
    if bool_status == 0:  # if the status code is 0, then the status is failed in maxon's documentation
        pass_state = "Fail"
    else:
        pass_state = "Pass"

    print("Operation status of: " + task + ": " + pass_state + " - Error code: " + str(pErrorCode.value))
    epos.VCS_GetErrorInfo(pErrorCode.value, byref(pErrorInfo), MaxStrSize)  # this doesn't work as expected
    print("Error information: " + str(pErrorInfo.value) + " " + str(hex(pErrorCode.value)))


# function: initialize_device
# purpose: intitializes device, resets faults, and sets device to be enabled
# parameters: keyhandle
# return: none
def initialize_device(key):

    # p1 = epos.VCS_ResetDevice(key, nodeID, byref(pErrorCode)) # uncomment to reset device
    # get_error("Reset device", p1)
    p1 = 1  # set to default value; resetting device not currently used
    p2 = epos.VCS_SetProtocolStackSettings(key, EPOS_BAUDRATE, EPOS_TIMEOUT, byref(pErrorCode))  # set baudrate
    get_error("Set protocol", p2)
    p3 = epos.VCS_ClearFault(key, nodeID, byref(pErrorCode))  # clear all faults
    get_error("Clear fault", p3)
    # p4 = epos.VCS_ActivateProfilePositionMode(key, nodeID, byref(pErrorCode)) # activate profile position mode
    # get_error("Activate profile position mode", p4)
    p4 = True
    p5 = epos.VCS_SetEnableState(key, nodeID, byref(pErrorCode))  # disable device
    get_error("Set enable state", p5)

    pIsInFault = c_uint()  # check if device is in fault state
    temp0 = epos.VCS_GetFaultState(keyHandle, nodeID, byref(pIsInFault), byref(pErrorCode))
    # if pIsInFault.value == 0:
    # print("Device is in fault state.")

    epos.VCS_SetMaxFollowingError(key, nodeID, 2500, byref(pErrorCode))

    # print(str(a.value) + ", " + str(b.value) + ", " + str(c.value) + ", ")
    epos.VCS_SetDcMotorParameter(keyHandle, nodeID, 6000, 10000, 48)

    return [p1, p2, p3, p4, p5]

def home():
    move_nudge("up", 1)
    pCurrent = c_short()

    #epos.VCS_SetHomingParameter(keyHandle, nodeID, HOMING_ACCELERATION, HOMING_SPEED, HOMING_SPEED, 0, 4294967295,0, byref(pErrorCode))

    epos.VCS_ActivateProfileVelocityMode(keyHandle, nodeID, byref(pErrorCode))
    epos.VCS_SetVelocityProfile(keyHandle, nodeID, 4294967295, 4294967295, byref(pErrorCode))
    stm.brake_set(False)
#            epos.VCS_FindHome(keyHandle, nodeID, -3, byref(pErrorCode))
    epos.VCS_MoveWithVelocity(keyHandle, nodeID, 1000, byref(pErrorCode))

    startT = timer()
    home_task = ni.startHome()
    while True:
        homed = home_task.read()
        epos.VCS_GetCurrentIs(keyHandle, nodeID, byref(pCurrent), byref(pErrorCode))

        if homed:
            time.sleep(.4)  # hit limit sw, but keep going a bit to bottom out
            epos.VCS_SetQuickStopState(keyHandle, nodeID, byref(pErrorCode))
            break
        if timer() - startT > 3:
             epos.VCS_SetQuickStopState(keyHandle, nodeID, byref(pErrorCode))
             break
        #maybe we should commented out because homing was having issues but maybe leave in cuz it might damage the motor if it operates for too long
    print("finish homing")
    stm.brake_set(True)
    home_task.stop()

    '''define current position as the new home'''
    epos.VCS_ActivateHomingMode(keyHandle, nodeID, byref(pErrorCode))
    epos.VCS_FindHome(keyHandle, nodeID, 35, byref(pErrorCode))

    startT = timer()
    while True:
        epos.VCS_DefinePosition(keyHandle, nodeID, c_long(0), byref(pErrorCode))
        if abs(get_position()) < 50:
            break
        if timer() - startT > 1:
            break
        time.sleep(.1)
    clear_errors()  # in case of fault, reset so it works
    globs.gui.current_pos_label.setText(str(get_position()))
    print(str(get_position()))



# function: plungeBegin
# purpose: runs the plunge cooler down at 19000 rpm (2 m/s) until the device faults and hits the hard stop
# parameters: self
# return: none
def plunge():
    print("pressseeed")
    print(abs(get_position()))
    if abs(get_position()) > 100: # outside bounds of normal plunge condition, not homere properly
        return
    print("forward")
    pptimer = timer()
    # resert global tracking variables
    globs.plungeData.clear()  # clear any previously collected data
    globs.plungeTime.clear()
    globs.plungePosData.clear()
    globs.plungeVelData=[]
    globs.plungeTemp.clear()
    globs.plunge_temp_time.clear()
    globs.gui.graphVel.clear()  # clear graph widget
    globs.gui.graphVelPos.clear()
    globs.gui.graphTempPos.clear()
    #globs.true_timepoint = 0

    # globs.gui.graphTempPos.setTitle("Plunge Cooler Temperature vs Time", color="w", size="10pt")
    # styles = {"color": "white", "font-size": "10px"}
    # globs.gui.graphTempPos.setLabel("left", "Voltage (V)", **styles)
    # globs.gui.graphTempPos.setLabel("bottom", "Time (s)", **styles)
    print(globs.gui.plungepause.isChecked())
    if globs.gui.plungepause.isChecked():
        #epos.VCS_SetEnableState(keyHandle, nodeID, byref(pErrorCode))  # enable device
        pp_wait_time = globs.gui.pp_time_box.value()
        # TODO: characterize how much extra t delay there is at beginning of PPP. might not be a huge deal
        if globs.gui.plungevac.isChecked() and globs.gui.vac_on_time.value() > pp_wait_time:
            globs.gui.vac_on_time.setEnabled(False)
            globs.gui.plungevac.setEnabled(False)  # any conflicting settings are off or set settings are kept constant
            wait_time = globs.gui.vac_on_time.value()  # read time to wait; turns on vacuum and pauses before plunge
            start = timer()
            ni.ni_set('vacuum', False)  # turn on vacuum
            while True:  # hold loop until time is reached, then plunge
                if timer() - start >= wait_time - pp_wait_time:
                    break
            globs.gui.vac_on_time.setEnabled(True)  # return previous settings to enable changes
            globs.gui.plungevac.setEnabled(True)
        print("nudged")
        move_nudge('down', globs.gui.plungepausedist.value())  # move to the distance

        if globs.gui.plungevac.isChecked() and globs.gui.vac_on_time.value() == pp_wait_time:
            ni.ni_set('vacuum', False)
        pptimer = timer()  # start timer for plunge pause plunge

        vac_on = False
        while True:  # hold in loop until pause time has been reached, then proceed to plunging stage
            if globs.gui.plungevac.isChecked() and ~vac_on and globs.gui.vac_on_time.value() < pp_wait_time and (
                    timer() - pptimer > globs.gui.vac_on_time.value()):
                ni.ni_set('vacuum', False)
                vac_on = True
            if timer() - pptimer > pp_wait_time:
                break
        epos.VCS_SetEnableState(keyHandle, nodeID, byref(pErrorCode))  # disable device
        move_plunge()  # arbitrary amount to ensure fault state reached; -ve is down
        ni.ni_set('vacuum', True)

    elif globs.gui.plungevac.isChecked():  # vacuum time; note that this does not add to the p-p-p time
        globs.gui.vac_on_time.setEnabled(False)
        globs.gui.plungevac.setEnabled(False)  # any conflicting settings are off or set settings are kept constant
        wait_time = globs.gui.vac_on_time.value()  # read time to wait; turns on vacuum and pauses before plunge
        start = timer()
        ni.ni_set('vacuum', False)  # turn on vacuum
        while True:  # hold loop until time is reached, then plunge
            if timer() - start >= wait_time or timer() - pptimer >= wait_time:
                epos.VCS_SetEnableState(keyHandle, nodeID, byref(pErrorCode))  # disable device
                move_plunge()  # arbitrary amount to ensure fault state reached; -ve is down
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
        epos.VCS_SetEnableState(keyHandle, nodeID, byref(pErrorCode))  # disable device
        move_plunge()  # arbitrary amount to ensure fault state reached; -ve is down

    tempcollect = timer()
    # while timer() - tempcollect < 1: # read concluding temperature for 1s
    #     plungeTemp.append(read_temperature())
    #     plunge_temp_time.append(timer() - temp_timer)

    globs.gui.graphTempPos.plot(globs.plunge_temp_time, globs.plungeTemp)  # this will repost the data after plunge

    value_n = (-1 * (get_position()-globs.pos_home_raw) * globs.leadscrew_inc / globs.encoder_pulse_num)  # approximate updated position
    globs.gui.current_pos_label.setText(str(value_n))  # update label with position
    globs.gui.graphVel.plot(globs.plungeTime, [pos * (globs.leadscrew_inc / globs.encoder_pulse_num) for pos in globs.plungePosData])  # plot collected data
    globs.gui.graphVelPos.plot([pos * (globs.leadscrew_inc / globs.encoder_pulse_num) for pos in globs.plungePosData], [vel * (globs.leadscrew_inc / globs.encoder_pulse_num) for vel in globs.plungeVelData])  # plot vel vs pos -- seet to plungePosData vs plungeData v vs pos
    stm.brake_set(False) #added to make the plunger go down fully
    # print(get_position())


# function: close_device
# purpose: closes maxon controller & ends program
# parameters: none
# return: none
def close_device(keyHandle):
    epos.VCS_SetDisableState(keyHandle, nodeID, byref(pErrorCode))  # disable device
    epos.VCS_CloseDevice(keyHandle, byref(pErrorCode))  # close device
    print("Device closed")


