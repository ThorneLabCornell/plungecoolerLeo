import globals as globs
from ctypes import *
import stm
import ni
import time
from timeit import default_timer as timer
import threading

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

keyHandle = epos.VCS_OpenDevice(b'EPOS2', b'MAXON SERIAL V2', b'USB', b'USB0',
                                byref(pErrorCode))  # specify EPOS version and interface

Configuration = 15  # configuration for digital input - General Purpose A

# Defining a variable NodeID and configuring connection
nodeID = 1  # set to 2; need to change depending on how the maxon controller is set up (check EPOS Studio)
EPOS_BAUDRATE = 1000000
EPOS_TIMEOUT = 500

# PID tuning
PID_P = 400000
PID_I = 1

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
def move_plunge(ppp = False):
    stop_position = int(globs.startWindow.brakeBox.value() + get_position()/2) # + b/c get_position returns a negative. comepnsates for offset in case of ppp
    print("stop pos:" + str(stop_position))
    timepoint_position = int((globs.a_position - globs.a_offset)/globs.A_STEPS_PER_UM)


    stm.clear_input()
    msg = '2' + str(stop_position).zfill(6) + str(timepoint_position).zfill(6) + '\r\n'

    stm.write(bytes(msg, 'utf-8'))
    #     x = ser.readline()  # command rx ack. start plunge
    #     print(x)

    # logT = threading.Thread(target=dataLogThread)
    # logT.start()
    if globs.readTemp_flag:
        tempT = threading.Thread(target=ni.tempLog)
        tempT.start()

    stm.brake_set(False)

    epos.VCS_SetVelocityRegulatorGain(keyHandle, nodeID, PID_P, PID_I, byref(pErrorCode))

    epos.VCS_SetMaxAcceleration(keyHandle, nodeID, 4294967295, byref(pErrorCode))
    epos.VCS_ActivateVelocityMode(keyHandle, nodeID, byref(pErrorCode))
    epos.VCS_SetVelocityMust(keyHandle, nodeID, globs.plunge_speed, byref(pErrorCode))

    # epos.VCS_ActivateProfileVelocityMode(keyHandle, nodeID, byref(pErrorCode))
    # epos.VCS_SetVelocityProfile(keyHandle, nodeID, 4294967295, 4294967295, byref(pErrorCode))
    # epos.VCS_MoveWithVelocity(keyHandle, nodeID, plunge_speed, byref(pErrorCode))

    start_time = timer()
    print("moved")

    stm.wait_for_ack()

    epos.VCS_SetQuickStopState(keyHandle, nodeID, byref(pErrorCode))

    print("done plunge")

    stm.receivePlungeData()

    # for soem reason the stm doesnt listen to the very first command after a plunge
    # TODO: fix this for real instead of a sketchy workaround
    # TODO tomorrow: fix this in the aforementioned sketchy way
    stm.reset()
    plunge_done_flag = True

    if globs.readTemp_flag:
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
    epos.VCS_ActivateProfilePositionMode(keyHandle, nodeID, byref(pErrorCode))
    epos.VCS_SetPositionProfile(keyHandle, nodeID, target_speed, acceleration, deceleration, byref(pErrorCode))  # set profile parameters
    epos.VCS_HaltPositionMovement(keyHandle, nodeID, byref(pErrorCode))
    time.sleep(.1)
    stm.brake_set(False)
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
def upNudgeFunc(self):

    epos.VCS_ActivateProfilePositionMode(keyHandle, nodeID, byref(pErrorCode))
    print("upnudge")
    move_nudge("up", self.nudge_spinbox.value())  # call function to move by nudge distance

    value_n = (-1 * (get_position()-globs.pos_home_raw) * globs.leadscrew_inc / globs.encoder_pulse_num) + self.nudge_spinbox.value() # approximate updated position
    self.current_pos_label.setText(value_n)  # update position label


# function: downNudgeFunc
# purpose: nudges the carriage down
# parameters: self
# return: none
def downNudgeFunc(self):
    epos.VCS_ActivateProfilePositionMode(keyHandle, nodeID, byref(pErrorCode))
    print(int(self.nudge_spinbox.value() / globs.leadscrew_inc * globs.encoder_pulse_num))
    move_nudge("down", self.nudge_spinbox.value())  # calculate nudge value from input & move

    value_n = (-1 * (get_position()-globs.pos_home_raw) * globs.leadscrew_inc / globs.encoder_pulse_num) + self.nudge_spinbox.value()  # approximate updated position

    self.current_pos_label.setText(str(value_n))  # update position label


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
    # a = c_long()
    # b = c_long()
    # c = c_long()
    # epos.VCS_GetDcMotorParameter(keyHandle, nodeID, byref(a), byref(b), byref(c), byref(pErrorCode))

    # print(str(a.value) + ", " + str(b.value) + ", " + str(c.value) + ", ")
    epos.VCS_SetDcMotorParameter(keyHandle, nodeID, 6000, 10000, 48)

    return [p1, p2, p3, p4, p5]

def home(self):
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
        print("current: " + str(pCurrent.value))
        if homed:# pCurrent.value <= 400 and (timer()-startT > .5):
            time.sleep(.4)  # hit limit sw, but keep going a bit to bottom out
            stm.brake_set(True)
            epos.VCS_SetQuickStopState(keyHandle, nodeID, byref(pErrorCode))
            break
        if timer() - startT > 3:
            epos.VCS_SetQuickStopState(keyHandle, nodeID, byref(pErrorCode))
            stm.brake_set(True)

            break
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
    clear_errors(keyHandle)  # in case of fault, reset so it works
    self.current_pos_label.setText(str(get_position()))
    print(str(get_position()))


# function: plungeBegin
# purpose: runs the plunge cooler down at 19000 rpm (2 m/s) until the device faults and hits the hard stop
# parameters: self
# return: none
def plunge(self):
    if abs(get_position()) > 50:
        return
    globs.plungeData.clear()  # clear any previously collected data
    globs.plungeTime.clear()
    globs.plungePosData.clear()
    globs.plungeTemp.clear()
    globs.plunge_temp_time.clear()
    pptimer = timer()
    self.graphVel.clear()  # clear graph widget
    self.graphVelPos.clear()
    self.graphTempPos.clear()

    self.graphTempPos.setTitle("Plunge Cooler Temperature vs Time", color="w", size="10pt")
    styles = {"color": "white", "font-size": "10px"}
    self.graphTempPos.setLabel("left", "Voltage (V)", **styles)
    self.graphTempPos.setLabel("bottom", "Time (s)", **styles)

    if self.plungepause.isChecked():

        epos.VCS_SetEnableState(keyHandle, nodeID, byref(pErrorCode))  # enable device
        pp_wait_time = self.pp_time_box.value()

        if self.plungevac.isChecked() and self.vac_on_time.value() > pp_wait_time:
            self.vac_on_time.setEnabled(False)
            self.plungevac.setEnabled(False)  # any conflicting settings are off or set settings are kept constant
            wait_time = self.vac_on_time.value()  # read time to wait; turns on vacuum and pauses before plunge
            start = timer()
            ni.ni_set('vacuum', False)  # turn on vacuum
            while True:  # hold loop until time is reached, then plunge
                if timer() - start >= wait_time - pp_wait_time:
                    break
            self.vac_on_time.setEnabled(True)  # return previous settings to enable changes
            self.plungevac.setEnabled(True)

        move_nudge('down', self.plungepausedist.value())  # move to the distance

        if self.plungevac.isChecked() and self.vac_on_time.value() == pp_wait_time:
            ni.ni_set('vacuum', False)
        pptimer = timer()  # start timer for plunge pause plunge

        vac_on = False
        while True:  # hold in loop until pause time has been reached, then proceed to plunging stage
            if self.plungevac.isChecked() and ~vac_on and self.vac_on_time.value() < pp_wait_time and (
                    timer() - pptimer > self.vac_on_time.value()):
                ni.ni_set('vacuum', False)
                vac_on = True
            if timer() - pptimer > pp_wait_time:
                break

        move_plunge(True)  # arbitrary amount to ensure fault state reached; -ve is down
        ni.ni_set('vacuum', True)

    elif self.plungevac.isChecked():  # vacuum time; note that this does not add to the p-p-p time
        self.vac_on_time.setEnabled(False)
        self.plungevac.setEnabled(False)  # any conflicting settings are off or set settings are kept constant
        wait_time = self.vac_on_time.value()  # read time to wait; turns on vacuum and pauses before plunge
        start = timer()
        ni.ni_set('vacuum', False)  # turn on vacuum
        while True:  # hold loop until time is reached, then plunge
            if timer() - start >= wait_time or timer() - pptimer >= wait_time:
                epos.VCS_SetEnableState(keyHandle, nodeID, byref(pErrorCode))  # disable device
                move_plunge()  # arbitrary amount to ensure fault state reached; -ve is down
                break
        ni.ni_set('vacuum', True)  # turn off vacuum following plunge
        self.vac_on_time.setEnabled(True)  # return previous settings to enable changes
        self.plungevac.setEnabled(True)

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

    self.graphTempPos.plot(globs.plunge_temp_time, globs.plungeTemp)  # this will repost the data after plunge

    value_n = (-1 * (get_position()-globs.pos_home_raw) * globs.leadscrew_inc / globs.encoder_pulse_num)  # approximate updated position
    self.current_pos_label.setText(str(value_n))  # update label with position
    self.graphVel.plot(globs.plungeTime, [pos * (globs.leadscrew_inc / globs.encoder_pulse_num) for pos in globs.plungePosData])  # plot collected data
    self.graphVelPos.plot(globs.plungePosData, globs.plungeData)  # plot vel vs pos -- seet to plungePosData vs plungeData v vs pos

    # print(get_position())


# function: close_device
# purpose: closes maxon controller & ends program
# parameters: none
# return: none
def close_device(key):
    epos.VCS_SetDisableState(keyHandle, nodeID, byref(pErrorCode))  # disable device
    epos.VCS_CloseDevice(keyHandle, byref(pErrorCode))  # close device
    print("Device closed")

