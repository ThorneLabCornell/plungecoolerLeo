"""
AUTHOR: KASHFIA (ASH) MAHMOOD
DATE: 06/14/2023
ACKNOWLEDGEMENTS: John Allen Indergaard for his sacrifices & Matt for his GUI praise
"""
import datetime
# import all necessary libraries
# region imports_and_constants


import pySerial
import numpy as np
import matplotlib.pyplot as plt
import os
import sys
import time
from timeit import default_timer as timer
import nidaqmx
from ctypes import *
import logging
import threading

# GUI imports
from PyQt6.QtCore import *
from PyQt6.QtGui import *
from PyQt6.QtWidgets import *
import pyqtgraph as pg
import qdarktheme
LEO_MODE = 1

# serial constants
# TODO: move these into a json or similar to easily share between python and stm32 scripts
ACK     = '1\r\n'
PLUNGE  = '2'
MOVE    = '3'
BRAKE   = '5'
RELEASE = '4'

# EPOS Library Path for commands - modify this if moving to a new computer
path = 'C:\\Program Files (x86)\\maxon motor ag\\EPOS IDX\\EPOS2\\04 Programming\\Windows DLL\\LabVIEW\\maxon EPOS\\Resources\EposCmd64.dll'

# Load library
cdll.LoadLibrary(path)
epos = CDLL(path)

# define return variables that are used globally
ret = 0
pErrorCode = c_uint()
pErrorInfo = c_char()
MaxStrSize = c_uint()
pDeviceErrorCode = c_uint()
DigitalInputNb = c_uint()
Configuration = 15  # configuration for digital input - General Purpose A

# Defining a variable NodeID and configuring connection
nodeID = 1  # set to 2; need to change depending on how the maxon controller is set up (check EPOS Studio)
EPOS_BAUDRATE = 1000000
EPOS_TIMEOUT = 500

# Configure desired motion profile
# acceleration should be 2g: 2*9.81m/s^2 -> 190 000
acceleration = 10000000  # rpm/s, up to 1e7 would be possible, 98 100 is 2g
deceleration = 10000000  # rpm/s

# NI DAQ configuration and pinout
DEVICE_NAME = "Dev1"
PINOUT = { # too lazy to implement and enum right now
    'brake':                DEVICE_NAME + "/port1/line2",
    'vacuum':               DEVICE_NAME + "/port0/line2",
    'heater':               DEVICE_NAME + "/port0/line3",
    'heater_controller':    DEVICE_NAME + "/port0/line6",
    'light':                DEVICE_NAME + "/port0/line3",
    'temperature':          DEVICE_NAME + "/ai10",
    'A_step':               DEVICE_NAME + "/port2/line4",
    'A_dir':                DEVICE_NAME + "/port2/line1",
    'A_en':                 DEVICE_NAME + "/port2/line6",
    'A_home':               DEVICE_NAME + "/port2/line0",
    'A_motor_power':        DEVICE_NAME + "/port0/line5",
    'thermocouple':         DEVICE_NAME + "/ai6"
}

# constants for A stepper motor
A_UP = True
A_DOWN = False
A_SPEED = .001
A_TRAVEL_LENGTH_STEPS = 10000000 # arbitrary right now
a_position = 10000 # global for a axis position tracking

readTemp_flag = False;

# global data collection
plungeTime = []
plungeData = []
plungeTemp = []
plungePosData = []
current_probe_temp = 0

leadscrew_inc = 1.2
encoder_pulse_num = 512 * 4

travel_length_pulses = 30000 # number of encoder pulses from top position to bottom position

HOMING_SPEED = 1000
HOMING_ACCELERATION = 5000

plunge_done_flag = False

prevPosData = 0
homePosDataPrev = 0
temp_timer = timer()
ultimate_timer = timer()
plunge_temp_time = []
pos_home_raw = 38000
read_time = True
val = 0  # temporary temperature storage

# endregion imports_and_constants

# incomplete
class TimerWindow(QWidget):
    def __init__(self):
        super().__init__()
        read_time = True
        self.setWindowTitle("Timer")  # set window title
        self.window_start_time = timer()
        self.super_timer = timer()
        layout = QVBoxLayout()
        self.label = QLabel("Time Elapsed: ")
        layout.addWidget(self.label)
        self.line = QLineEdit(self)
        layout.addWidget(self.line)
        self.setLayout(layout)
        timeconnect = QTimer(self)
        timeconnect.timeout.connect(self.update_line)
        timeconnect.start()

    def update_line(self):
        if read_time:
            self.super_timer = timer()
            self.line.setText("%4.4f" % (self.super_timer - self.window_start_time))

    def closeEvent(self, a0):
        self.close()


# initialize the main window - class which contains all the initialization, GUI components, et cetera
class MainWindow(QMainWindow):  # subclassing Qt class

    def __init__(self):
        super(MainWindow, self).__init__()  # must call when subclassing to let Qt set up object
        # self.setFixedSize(QSize(850, 600))  # set window size
        self.setWindowTitle("Plunge Cooler")  # set window title

        # create tabs
        self.tabs = QTabWidget()
        self.tabs.setTabPosition(QTabWidget.TabPosition.North)  # set position of the tab to be on top
        # will need another tab if alternative settings are desired in one GUI
        # will need another tab if alternative settings are desired in one GUI
        self.tab1 = self.plunge_options()  # instantiate the GroupBox and set it as a tab widget
        self.tab2 = self.ABox()
        self.tab3 = self.controlBox()
        self.tabs.addTab(self.tab1, 'Plunge')
        self.tabs.addTab(self.tab2, 'A Axis')
        self.tabs.addTab(self.tab3, "Control Panel")
        self.setCentralWidget(self.tabs)  # set the tab array to be the central widget

    # function: plunge_options
    # purpose: create a GUI interface for plunging (tab1)
    # parameters: self
    # return: GroupBox
    def plunge_options(self):
        # set layout as grid
        layout = QGridLayout()
        # create a GroupBox to hold the layout overall
        groupBox = QGroupBox()
        self.widget_nudge = self.nudgeBox()
        self.widget_plunge = self.plungeBox()
        self.setup_settings = self.setupBox()
        self.vac_settings = self.setupBox2()
        self.graphs = self.graphBox()

        subBox = QGroupBox()
        vbox = QHBoxLayout()
        vbox.addWidget(self.setup_settings)
        vbox.addWidget(self.vac_settings)
        vbox.setAlignment(Qt.AlignmentFlag.AlignTop)
        vbox.setSpacing(10)
        subBox.setLayout(vbox)

        graphBox = QGroupBox()
        vbox2 = QVBoxLayout()
        vbox2.addWidget(subBox)
        vbox2.addWidget(self.graphs)
        vbox2.setAlignment(Qt.AlignmentFlag.AlignTop)
        vbox2.setSpacing(10)
        graphBox.setLayout(vbox2)

        # place the GroupBoxes above into a grid layout: x, y indicates position in the grid
        layout.addWidget(self.widget_plunge, 0, 0)
        layout.addWidget(self.widget_nudge, 0, 1)
        layout.addWidget(graphBox, 0, 2)
        # set layout for the GroupBox
        groupBox.setLayout(layout)

        # return the GroupBox to the initialization function
        return groupBox

    # region plungeBox_and_func

    # function: plungeBox
    # purpose: create buttons and tie functions to plunge and home the plunge cooler
    # parameters: self
    # return: GroupBox
    def plungeBox(self):
        # create GroupBox to contain buttons
        groupBox = QGroupBox("Operations")

        # create settings for homeButton
        self.homeButton = QPushButton(self)
        self.homeButton.setFixedSize(300, 300)
        self.homeButton.setFont(QFont('Munhwa Gothic', 40))
        self.homeButton.setText("HOME")
        self.homeButton.setStyleSheet('''
                            QPushButton {
                                color: white; background-color : #2E8B57; border-radius : 150px;
                                border : 0px solid black; font-weight : bold;
                            }
                            QPushButton:pressed {
                                color: white; background-color : #1e5e3a; border-radius : 150px;
                                border : 0px solid black; font-weight : bold;                               
                            }
                            QPushButton:disabled {
                                background-color: gray;
                            }
                            ''')
        self.homeButton.pressed.connect(self.homeBegin)  # connect the button the operation function

        # create settings for plungeButton
        self.plungeButton = QPushButton(self)
        self.plungeButton.setFixedSize(300, 300)
        self.plungeButton.setFont(QFont('Munhwa Gothic', 40))
        self.plungeButton.setText("PLUNGE")
        self.plungeButton.setStyleSheet('''
                            QPushButton {
                                color: white; background-color : #AA4A44; border-radius : 150px;
                                border : 0px solid black; font-weight : bold;
                            }
                            QPushButton:pressed {
                                color: white; background-color : #803833; border-radius : 150px;
                                border : 0px solid black; font-weight : bold;                               
                            }
                            QPushButton:disabled {
                                background-color: gray;
                            }
                            ''')
        self.plungeButton.pressed.connect(self.plungeBegin)  # tie button to plunging operation

        self.timer_button = QPushButton()
        self.timer_button.setText("Show timer")
        self.timer_button.pressed.connect(self.open_timer_box)

        # create a vertical box layout - stacks QWidgets vertically
        vbox = QVBoxLayout()
        # add widgets to vbox
        vbox.addWidget(self.homeButton)
        vbox.addWidget(self.plungeButton)
        vbox.addWidget(self.timer_button)

        # set vbox to align at the center and top
        vbox.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        # set spacing between widgets
        vbox.setSpacing(40)
        groupBox.setLayout(vbox)
        return groupBox

    # function: homeBegin
    # purpose: runs the plunge cooler up until the device faults to home; would want to implement sensor later
    # parameters: self
    # return: none
    def homeBegin(self):
        move_nudge('up', 1)

        if LEO_MODE:
            pCurrent = c_short()

            epos.VCS_SetHomingParameter(keyHandle, nodeID, HOMING_ACCELERATION, HOMING_SPEED, HOMING_SPEED, 0, 0, 0, byref(pErrorCode))
            epos.VCS_ActivateHomingMode(keyHandle, nodeID, byref(pErrorCode))
            brake_set(False)
            ni_set('light', True)
            epos.VCS_FindHome(keyHandle, nodeID, 23, byref(pErrorCode))
            startT = timer()
            while True:
                epos.VCS_GetCurrentIs(keyHandle, nodeID, byref(pCurrent), byref(pErrorCode))
                print("current: " + str(pCurrent.value))
                if pCurrent.value <= 400 and (timer()-startT > .05): #not mving, hit switch
                    break
                if timer() - startT > 5:
                    break
            brake_set(True)
            ni_set('light', False)

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
    def plungeBegin(self):
        if abs(int(self.current_pos_label.text())) > 50:
            return
        ni_set('light', True)  # turn light on to show movement
        plungeData.clear()  # clear any previously collected data
        plungeTime.clear()
        plungePosData.clear()
        plungeTemp.clear()
        plunge_temp_time.clear()
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
                ni_set('vacuum', False)  # turn on vacuum
                while True:  # hold loop until time is reached, then plunge
                    if timer() - start >= wait_time - pp_wait_time:
                        break
                self.vac_on_time.setEnabled(True)  # return previous settings to enable changes
                self.plungevac.setEnabled(True)

            move_nudge('down', self.plungepausedist.value())  # move to the distance

            if self.plungevac.isChecked() and self.vac_on_time.value() == pp_wait_time:
                ni_set('vacuum', False)
            pptimer = timer()  # start timer for plunge pause plunge

            vac_on = False
            while True:  # hold in loop until pause time has been reached, then proceed to plunging stage
                if self.plungevac.isChecked() and ~vac_on and self.vac_on_time.value() < pp_wait_time and (
                        timer() - pptimer > self.vac_on_time.value()):
                    ni_set('vacuum', False)
                    vac_on = True
                if timer() - pptimer > pp_wait_time:
                    break

            move_plunge()  # arbitrary amount to ensure fault state reached; -ve is down
            ni_set('vacuum', True)

        elif self.plungevac.isChecked():  # vacuum time; note that this does not add to the p-p-p time
            self.vac_on_time.setEnabled(False)
            self.plungevac.setEnabled(False)  # any conflicting settings are off or set settings are kept constant
            wait_time = self.vac_on_time.value()  # read time to wait; turns on vacuum and pauses before plunge
            start = timer()
            ni_set('vacuum', False)  # turn on vacuum
            while True:  # hold loop until time is reached, then plunge
                if timer() - start >= wait_time or timer() - pptimer >= wait_time:
                    epos.VCS_SetEnableState(keyHandle, nodeID, byref(pErrorCode))  # disable device
                    move_plunge()  # arbitrary amount to ensure fault state reached; -ve is down
                    break
            ni_set('vacuum', True)  # turn off vacuum following plunge
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

        self.graphTempPos.plot(plunge_temp_time, plungeTemp)  # this will repost the data after plunge

        ni_set('light', False)  # turn off light
        value_n = (-1 * (get_position()-pos_home_raw) * leadscrew_inc / encoder_pulse_num)  # approximate updated position
        self.current_pos_label.setText("%4.2f cm" % (value_n))  # update label with position
        self.graphVel.plot(plungeTime, plungeData)  # plot collected data
        self.graphVelPos.plot(plungePosData, plungeData)  # plot vel vs pos -- seet to plungePosData vs plungeData v vs pos

        # print(get_position())

    # endregion plungeBox_and_func

    def open_timer_box(self):
        self.w = TimerWindow()
        ultimate_timer = timer()
        self.w.show()

    # region nudgeBox_and_func

    # function: nudgeBox
    # purpose: creates middle GUI for nudge settings & position label
    # parameters: self
    # return: GroupBox
    def nudgeBox(self):
        groupBox = QGroupBox("Nudge")  # create GroupBox to hold QWidgets

        # create button to initiate nudge: this button will set device enable states and disable home/plunge buttons
        self.startNudge = QPushButton(self)
        self.startNudge.setFixedSize(300, 300)
        self.startNudge.setFont(QFont('Munhwa Gothic', 40))
        self.startNudge.setText("NUDGE")
        self.startNudge.setStyleSheet('''
                            QPushButton {
                                color: white; background-color : #4682B4; border-radius : 150px;
                                border : 0px solid black; font-weight : bold;
                            }
                            QPushButton:pressed {
                                color: white; background-color : #0F52BA; border-radius : 150px;
                                border : 0px solid black; font-weight : bold;                               
                            }
                            QPushButton:disabled {
                                background-color: gray;
                            }
                            ''')

        # create button to nudge upwards
        self.upNudge = QPushButton(self)
        self.upNudge.setFixedSize(300, 100)
        self.upNudge.setFont(QFont('Calibri', 30))
        self.upNudge.setText("↑")
        self.upNudge.setStyleSheet('''
                            QPushButton {
                                color: white; background-color : #CC7722; border-radius : 20px;
                                border : 0px solid black; font-weight : bold;
                            }
                            QPushButton:pressed {
                                color: white; background-color : #99520c; border-radius : 20px;
                                border : 0px solid black; font-weight : bold;                               
                            }
                            QPushButton:disabled {
                                background-color: gray;
                            }
                            ''')

        # create button to stop nudge process to enable plunge/home capabilities
        self.stopButton = QPushButton(self)
        self.stopButton.setFixedSize(300, 100)
        self.stopButton.setFont(QFont('Munhwa Gothic', 30))
        self.stopButton.setText("STOP")
        self.stopButton.setStyleSheet('''
                            QPushButton {
                                color: white; background-color : #AA4A44; border-radius : 20px;
                                border : 0px solid black; font-weight : bold;
                            }
                            QPushButton:pressed {
                                color: white; background-color : #803833; border-radius : 20px;
                                border : 0px solid black; font-weight : bold;                               
                            }
                            QPushButton:disabled {
                                background-color: gray;
                            }
                            }
                            ''')

        # create button to nudge downwards
        self.downNudge = QPushButton(self)
        self.downNudge.setFixedSize(300, 100)
        self.downNudge.setFont(QFont('Calibri', 30))
        self.downNudge.setText("↓")
        self.downNudge.setStyleSheet('QPushButton{color: white}')
        self.downNudge.setStyleSheet('''
                            QPushButton {
                                color: white; background-color : #CC7722; border-radius : 20px;
                                border : 0px solid black; font-weight : bold;
                            }
                            QPushButton:pressed {
                                color: white; background-color : #99520c; border-radius : 20px;
                                border : 0px solid black; font-weight : bold;                               
                            }
                            QPushButton:disabled {
                                background-color: gray;
                            }
                            ''')

        # create label to indicate where to input nudge distance
        self.nudge_spin_label = QLabel(self)
        self.nudge_spin_label.setText("Set nudge distance")
        self.nudge_spin_label.setFont(QFont('Munhwa Gothic', 20))

        # create DoubleSpinBox (can hold float values) to indicate desired nudge distance & set associated settings
        self.nudge_spinbox = QDoubleSpinBox(self)
        self.nudge_spinbox.setMaximum(20)  # max nudge value
        self.nudge_spinbox.setMinimum(0.1)  # min nudge value
        self.nudge_spinbox.setValue(2)  # default value
        self.nudge_spinbox.setSingleStep(0.1)  # incremental/decremental value when arrows are pressed
        self.nudge_spinbox.setSuffix(" cm")  # show a suffix (this is not read into the __.value() func)
        self.nudge_spinbox.setFont(QFont('Munhwa Gothic', 40))
        self.nudge_spinbox.setStyleSheet('''
                            QSpinBox::down-button{width: 400px}
                            QSpinBox::up-button{width: 400px}
                            ''')

        # create a label holding the positional data
        self.current_pos_label = QLabel(self)
        # note: this method of setting distance should be modified. takes a manually derived pos_home position
        # value which indicates home, then subtracts it from the current position read by the encoder
        self.current_pos_label.setText("Home to initialize position collection.")  # If inaccurate, home,
        # press E-STOP, unpress, then restart program.
        self.current_pos_label.setMaximumSize(300, 100)
        self.current_pos_label.setFont(QFont('Munhwa Gothic', 20))
        self.current_pos_label.setWordWrap(True)

        # connect buttons to associated functions
        # note: pressed allows to read when a button is initially clicked, clicked only runs func after release
        self.startNudge.clicked.connect(self.nudgeBegin)
        self.upNudge.pressed.connect(self.upNudgeFunc)
        self.stopButton.clicked.connect(self.stopNudge)
        self.downNudge.pressed.connect(self.downNudgeFunc)

        # set up and down nudge to autorepeat (holding will call func multiple times), disable buttons,
        # and be able to read if button is help (checkable status)
        #self.upNudge.setAutoRepeat(True)
        self.upNudge.setEnabled(False)
        self.upNudge.setCheckable(True)
        #self.downNudge.setAutoRepeat(True)
        self.downNudge.setEnabled(False)
        self.downNudge.setCheckable(True)

        # disable stop button
        self.stopButton.setEnabled(False)

        # create vertical box layout
        vbox = QVBoxLayout()
        # add widgets to the box
        vbox.addWidget(self.startNudge)
        vbox.addWidget(self.upNudge)
        vbox.addWidget(self.stopButton)
        vbox.addWidget(self.downNudge)
        vbox.addWidget(self.nudge_spin_label)
        vbox.addWidget(self.nudge_spinbox)
        vbox.addWidget(self.current_pos_label)
        # set alignment flags
        vbox.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        # set spacing between widgets
        vbox.setSpacing(20)
        groupBox.setLayout(vbox)  # set layout for groupBox
        return groupBox

    # function: nudgeBegin
    # purpose: initializes the device to receive nudge inputs via the buttons & disables plunge functionality
    # parameters: self
    # return: none
    def nudgeBegin(self):
        # ni_set('light', True)  # turn on light to indicate movement stage
        # disable plunge, home, startNudge buttons, enable control buttons and stop nudge buttons
        self.homeButton.setEnabled(False)
        self.plungeButton.setEnabled(False)
        self.startNudge.setEnabled(False)
        self.upNudge.setEnabled(True)
        self.stopButton.setEnabled(True)
        self.downNudge.setEnabled(True)
        # enable device - this will hold the device where it is, but can also be hard on the motor
        epos.VCS_SetEnableState(keyHandle, nodeID, byref(pErrorCode))  # disable device

    # function: upNudgeFunc
    # purpose: nudges the carriage up
    # parameters: self
    # return: none
    def upNudgeFunc(self):

        epos.VCS_ActivateProfilePositionMode(keyHandle, nodeID, byref(pErrorCode))
        print("upnudge")
        move_nudge("up", self.nudge_spinbox.value())  # call function to move by nudge distance

        value_n = (-1 * (get_position()-pos_home_raw) * leadscrew_inc / encoder_pulse_num) + self.nudge_spinbox.value() # approximate updated position
        self.current_pos_label.setText(str(get_position()))  # update position label

    # function: stopNudge
    # purpose: stops nudge function
    # parameters: self
    # return: none
    def stopNudge(self):
        # reset settings to enable plunging and disable nudging
        ni_set('light', False)


        self.startNudge.setEnabled(True)
        self.homeButton.setEnabled(True)
        self.plungeButton.setEnabled(True)
        self.upNudge.setEnabled(False)
        self.stopButton.setEnabled(False)
        self.downNudge.setEnabled(False)

        # reinitialize device and set it to disabled
        clear_errors(keyHandle)

    # function: downNudgeFunc
    # purpose: nudges the carriage down
    # parameters: self
    # return: none
    def downNudgeFunc(self):
        epos.VCS_ActivateProfilePositionMode(keyHandle, nodeID, byref(pErrorCode))
        print(int(self.nudge_spinbox.value() / leadscrew_inc * encoder_pulse_num))
        move_nudge("down", self.nudge_spinbox.value())  # calculate nudge value from input & move

        value_n = (-1 * (get_position()-pos_home_raw) * leadscrew_inc / encoder_pulse_num) + self.nudge_spinbox.value()  # approximate updated position

        self.current_pos_label.setText(str(get_position()))  # update position label

    # endregion nudgeBox_and_func

    # region A_axis

    # function: ABox
    # purpose: creates middle GUI for A axis control
    # parameters: self
    # return: GroupBox
    def ABox(self):
        groupBox = QGroupBox("Nudge")  # create GroupBox to hold QWidgets

        # create button to initiate nudge: this button will set device enable states and disable home/plunge buttons
        self.A_start = QPushButton(self)
        self.A_start.setFixedSize(300, 300)
        self.A_start.setFont(QFont('Munhwa Gothic', 40))
        self.A_start.setText("A AXIS")
        self.A_start.setStyleSheet('''
                            QPushButton {
                                color: white; background-color : #4682B4; border-radius : 15px;
                                border : 0px solid black; font-weight : bold;
                            }
                            QPushButton:pressed {
                                color: white; background-color : #0F52BA; border-radius : 15px;
                                border : 0px solid black; font-weight : bold;                               
                            }
                            QPushButton:disabled {
                                background-color: gray;
                            }
                            ''')

        self.A_home = QPushButton(self)
        self.A_home.setFixedSize(300, 300)
        self.A_home.setFont(QFont('Munhwa Gothic', 40))
        self.A_home.setText("A HOME")
        self.A_home.setStyleSheet('''
                                    QPushButton {
                                        color: white; background-color : #4682B4; border-radius : 15px;
                                        border : 0px solid black; font-weight : bold;
                                    }
                                    QPushButton:pressed {
                                        color: white; background-color : #0F52BA; border-radius : 15px;
                                        border : 0px solid black; font-weight : bold;                               
                                    }
                                    QPushButton:disabled {
                                        background-color: gray;
                                    }
                                    ''')

        # create button to nudge upwards
        self.A_up = QPushButton(self)
        self.A_up.setFixedSize(300, 100)
        self.A_up.setFont(QFont('Calibri', 30))
        self.A_up.setText("↑")
        self.A_up.setStyleSheet('''
                            QPushButton {
                                color: white; background-color : #CC7722; border-radius : 20px;
                                border : 0px solid black; font-weight : bold;
                            }
                            QPushButton:pressed {
                                color: white; background-color : #99520c; border-radius : 20px;
                                border : 0px solid black; font-weight : bold;                               
                            }
                            QPushButton:disabled {
                                background-color: gray;
                            }
                            ''')

        # create button to stop nudge process to enable plunge/home capabilities
        self.A_stop = QPushButton(self)
        self.A_stop.setFixedSize(300, 100)
        self.A_stop.setFont(QFont('Munhwa Gothic', 30))
        self.A_stop.setText("STOP")
        self.A_stop.setStyleSheet('''
                            QPushButton {
                                color: white; background-color : #AA4A44; border-radius : 20px;
                                border : 0px solid black; font-weight : bold;
                            }
                            QPushButton:pressed {
                                color: white; background-color : #803833; border-radius : 20px;
                                border : 0px solid black; font-weight : bold;                               
                            }
                            QPushButton:disabled {
                                background-color: gray;
                            }
                            ''')

        # create button to nudge downwards
        self.A_down = QPushButton(self)
        self.A_down.setFixedSize(300, 100)
        self.A_down.setFont(QFont('Calibri', 30))
        self.A_down.setText("↓")
        self.A_down.setStyleSheet('QPushButton{color: white}')
        self.A_down.setStyleSheet('''
                            QPushButton {
                                color: white; background-color : #CC7722; border-radius : 20px;
                                border : 0px solid black; font-weight : bold;
                            }
                            QPushButton:pressed {
                                color: white; background-color : #99520c; border-radius : 20px;
                                border : 0px solid black; font-weight : bold;                               
                            }
                            QPushButton:disabled {
                                background-color: gray;
                            }
                            ''')

        self.A_move_to = QPushButton(self)
        self.A_move_to.setFixedSize(300, 340)
        self.A_move_to.setFont(QFont('Calibri', 30))
        self.A_move_to.setText("Move To")
        self.A_move_to.setStyleSheet('QPushButton{color: white}')
        self.A_move_to.setStyleSheet('''
                            QPushButton {
                                color: white; background-color : #CC7722; border-radius : 20px;
                                border : 0px solid black; font-weight : bold;
                            }
                            QPushButton:pressed {
                                color: white; background-color : #99520c; border-radius : 20px;
                                border : 0px solid black; font-weight : bold;                               
                            }
                            QPushButton:disabled {
                                background-color: gray;
                            }
                            ''')


        # create label to indicate where to input nudge distance
        self.A_spin_label = QLabel(self)
        self.A_spin_label.setText("Set nudge distance")
        self.A_spin_label.setFont(QFont('Munhwa Gothic', 20))

        self.A_spin_label_2 = QLabel(self)
        self.A_spin_label_2.setText("Set move to position")
        self.A_spin_label_2.setFont(QFont('Munhwa Gothic', 20))

        self.A_spinbox_2 = QDoubleSpinBox(self)
        self.A_spinbox_2.setMaximum(A_TRAVEL_LENGTH_STEPS)  # max nudge value
        self.A_spinbox_2.setMinimum(0)  # min nudge value
        self.A_spinbox_2.setValue(200)  # default value
        self.A_spinbox_2.setSingleStep(1)  # incremental/decremental value when arrows are pressed
        # self.A_spinbox_2.setSuffix(" cm")  # show a suffix (this is not read into the __.value() func)
        self.A_spinbox_2.setFont(QFont('Munhwa Gothic', 40))
        self.A_spinbox_2.setStyleSheet('''
                                    QSpinBox::down-button{width: 400px}
                                    QSpinBox::up-button{width: 400px}
                                    ''')

        # create DoubleSpinBox (can hold float values) to indicate desired nudge distance & set associated settings
        self.A_spinbox = QDoubleSpinBox(self)
        self.A_spinbox.setMaximum(A_TRAVEL_LENGTH_STEPS)  # max nudge value
        self.A_spinbox.setMinimum(1)  # min nudge value
        self.A_spinbox.setValue(200)  # default value
        self.A_spinbox.setSingleStep(1)  # incremental/decremental value when arrows are pressed
        #self.A_spinbox.setSuffix(" cm")  # show a suffix (this is not read into the __.value() func)
        self.A_spinbox.setFont(QFont('Munhwa Gothic', 40))
        self.A_spinbox.setStyleSheet('''
                            QSpinBox::down-button{width: 400px}
                            QSpinBox::up-button{width: 400px}
                            ''')

        # create a label holding the positional data
        self.A_pos_label = QLabel(self)
        # note: this method of setting distance should be modified. takes a manually derived pos_home position
        # value which indicates home, then subtracts it from the current position read by the encoder
        self.A_pos_label.setText("Home to initialize position collection.")  # If inaccurate, home,
        # press E-STOP, unpress, then restart program.
        self.A_pos_label.setMaximumSize(300, 100)
        self.A_pos_label.setFont(QFont('Munhwa Gothic', 20))
        self.A_pos_label.setWordWrap(True)

        # connect buttons to associated functions
        # note: pressed allows to read when a button is initially clicked, clicked only runs func after release
        self.A_start.clicked.connect(self.A_start_func)
        self.A_up.pressed.connect(self.A_up_func)
        self.A_stop.clicked.connect(self.A_stop_func)
        self.A_down.pressed.connect(self.A_down_func)
        self.A_home.clicked.connect(self.A_home_func)
        self.A_move_to.clicked.connect(self.A_move_to_func)

        # set up and down nudge to autorepeat (holding will call func multiple times), disable buttons,
        # and be able to read if button is help (checkable status)
        self.A_up.setAutoRepeat(False)
        self.A_up.setEnabled(False)
        self.A_up.setCheckable(True)
        self.A_down.setAutoRepeat(False)
        self.A_down.setEnabled(False)
        self.A_down.setCheckable(True)
        self.A_stop.setEnabled(False)
        self.A_home.setEnabled(False)
        self.A_move_to.setEnabled(False)



        # create vertical box layout
        vbox = QGridLayout()
        # add widgets to the box
        vbox.addWidget(self.A_start, 0, 0)
        vbox.addWidget(self.A_up, 1, 0)
        vbox.addWidget(self.A_stop, 2, 0)
        vbox.addWidget(self.A_down, 3, 0)
        vbox.addWidget(self.A_spin_label, 4, 0)
        vbox.addWidget(self.A_spinbox, 5, 0)

        vbox.addWidget(self.A_home, 0, 1)
        vbox.addWidget(self.A_move_to, 1, 1, 3, 0)
        vbox.addWidget(self.A_spin_label_2, 4, 1)
        vbox.addWidget(self.A_spinbox_2, 5, 1)

        vbox.addWidget(self.A_pos_label, 6, 0, 0, 2)

        # set alignment flags
        vbox.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        # set spacing between widgets
        vbox.setSpacing(20)
        groupBox.setLayout(vbox)  # set layout for groupBox
        return groupBox

    # function: nudgeBegin
    # purpose: initializes the device to receive nudge inputs via the buttons & disables plunge functionality
    # parameters: self
    # return: none
    def A_start_func(self):
        ni_set('A_en', True)
        # ni_set('light', True)  # turn on light to indicate movement stage
        # disable plunge, home, startNudge buttons, enable control buttons and stop nudge buttons
        self.A_home.setEnabled(True)
        self.A_up.setEnabled(True)
        self.A_stop.setEnabled(True)
        self.A_down.setEnabled(True)
        self.A_move_to.setEnabled(True)

        # enable device - this will hold the device where it is, but can also be hard on the motor
        epos.VCS_SetEnableState(keyHandle, nodeID, byref(pErrorCode))  # disable device

    # function: A_up_func
    # purpose: nudges the carriage up
    # parameters: self
    # return: none
    def A_up_func(self):
        global a_position
        new_pos = a_position + int(self.A_spinbox.value())
        A_move(A_UP, int(self.A_spinbox.value()))
        a_position = new_pos
        self.current_pos_label.setText(str(new_pos))  # update position label


    # function: A_stop_func
    # purpose: stops nudge function
    # parameters: self
    # return: none
    def A_stop_func(self):
        ni_set('A_en', False)
        ni_set('A_motor_power', False)

        self.A_up.setEnabled(False)
        self.A_stop.setEnabled(False)
        self.A_down.setEnabled(False)
        self.A_home.setEnabled(False)
        self.A_move_to.setEnabled(False)



    # function: downNudgeFunc
    # purpose: nudges the carriage down
    # parameters: self
    # return: none
    def A_down_func(self):
        global a_position
        new_pos = a_position - int(self.A_spinbox.value())
        A_move(A_DOWN, int(self.A_spinbox.value()))
        a_position = new_pos
        self.A_pos_label.setText(str(new_pos))  # update position label


    def A_home_func(self):
        global a_position
        ni_set('A_motor_power', True)
        ni_set('A_dir', A_DOWN)
        step_task = nidaqmx.Task()
        step_task.do_channels.add_do_chan(PINOUT['A_step'])
        step_task.start()
        home_task = nidaqmx.Task()
        home_task.di_channels.add_di_chan(PINOUT['A_home'])
        home_task.start()
        while True:
            step_task.write(True)
            time.sleep(A_SPEED)
            step_task.write(False)
            time.sleep(A_SPEED)
            if home_task.read():
                break
        a_position = 0
        self.A_pos_label.setText(str(0))

        home_task.stop()
        step_task.stop()
        ni_set('A_motor_power', False)


    def A_move_to_func(self):
        global a_position
        to_pos = int(self.A_spinbox_2.value())
        direction = A_UP if to_pos > a_position else A_DOWN
        amount = abs(a_position - to_pos)
        A_move(direction, amount)
        a_position = to_pos

    # endregion nudgeBox_and_func

    # region control_panel
    def controlBox(self):
        groupBox = QGroupBox("Controls")  # create a GroupBox

        self.brakeButton = QCheckBox(self)
        self.brakeButton.setText("BRAKE TOGGLE")
        self.brakeButton.setFont(QFont('Munhwa Gothic', 30))
        self.brakeButton.setStyleSheet("QCheckBox::indicator"
                                   "{"
                                   "width : 70px;"
                                   "height : 70px;"
                                   "}")
        self.brakeButton.stateChanged.connect(self.brakeFunc)

        self.tempButton = QCheckBox(self)
        self.tempButton.setText("TEMP TOGGLE")
        self.tempButton.setFont(QFont('Munhwa Gothic', 30))
        self.tempButton.setStyleSheet("QCheckBox::indicator"
                                   "{"
                                   "width : 70px;"
                                   "height : 70px;"
                                   "}")
        self.tempButton.stateChanged.connect(self.tempToggle)

        self.timepointBox = QDoubleSpinBox(self)
        self.timepointBox.setMaximum(40000)  # max nudge value
        self.timepointBox.setMinimum(1)  # min nudge value
        self.timepointBox.setValue(200)  # default value
        self.timepointBox.setSingleStep(1)  # incremental/decremental value when arrows are pressed
        # self.timepointBox.setSuffix(" cm")  # show a suffix (this is not read into the __.value() func)
        self.timepointBox.setFont(QFont('Munhwa Gothic', 40))
        self.timepointBox.setStyleSheet('''
                                    QSpinBox::down-button{width: 400px}
                                    QSpinBox::up-button{width: 400px}
                                    ''')

        vbox = QVBoxLayout()

        vbox.addWidget(self.brakeButton)
        vbox.addWidget(self.tempButton)

        vbox2 = QVBoxLayout()
        vbox2.addWidget(self.timepointBox)

        # set alignment, spacing, and assign layout to groupBox
        vbox.setAlignment(Qt.AlignmentFlag.AlignTop)
        vbox.setSpacing(10)
        vbox2.setAlignment(Qt.AlignmentFlag.AlignTop)
        vbox2.setSpacing(10)


        hbox = QHBoxLayout()
        hbox.addWidget(vbox)
        hbox.addWidget(vbox2)
        hbox.setSpacing(50)

        groupBox.setLayout(hbox)
        return groupBox


    def brakeFunc(self):
        brake_set(self.brakeButton.isChecked())

    def tempToggle(self):
        global readTemp_flag
        readTemp_flag = self.tempButton.isChecked()

    # endregion control_panel
    # region setup_funcs

    # function: setupBox
    # purpose: create widgets for plunge settings/control options
    # parameters: self
    # return: GroupBox
    def setupBox(self):
        groupBox = QGroupBox("Controls")  # create a GroupBox
        self.h_controller_check = QCheckBox(self)  # create a checkbox for turning on heater controller
        self.h_controller_check.setText("HEATER CONTROL")
        self.h_controller_check.setFont(QFont('Munhwa Gothic', 30))
        self.h_controller_check.setStyleSheet("QCheckBox::indicator"
                                              "{"
                                              "width : 70px;"
                                              "height : 70px;"
                                              "}")

        # create checkbox for heater
        self.h_power = QCheckBox(self)
        self.h_power.setText("HEATER")
        self.h_power.setFont(QFont('Munhwa Gothic', 30))
        self.h_power.setStyleSheet("QCheckBox::indicator"
                                   "{"
                                   "width : 70px;"
                                   "height : 70px;"
                                   "}")

        # create checkbox for vacuum continuously on
        self.vac = QCheckBox(self)
        self.vac.setText("VACUUM")
        self.vac.setFont(QFont('Munhwa Gothic', 30))
        self.vac.setStyleSheet("QCheckBox::indicator"
                               "{"
                               "width : 70px;"
                               "height : 70px;"
                               "}")

        self.spacerlabel = QLabel("")
        self.spacerlabel.setFont(QFont('Munhwa Fothic', 137))

        # connect checkboxes to functions - update when checkbox value is changed
        self.h_controller_check.stateChanged.connect(self.guiheater_controller)
        self.h_power.stateChanged.connect(self.guiheater_power)
        self.vac.stateChanged.connect(self.guivacuum)

        # set enable state of checkboxes
        self.h_controller_check.setEnabled(True)
        self.h_power.setEnabled(True)
        self.vac.setEnabled(True)


        # create graph widget to read temperature; updates in plunge stage
        self.graphTempPos = pg.PlotWidget(self)
        self.graphTempPos.setBackground('black')
        self.graphTempPos.setTitle("Plunge Cooler Temperature vs Position", color="w", size="10pt")
        styles = {"color": "white", "font-size": "10px"}
        self.graphTempPos.setLabel("left", "Voltage (V)", **styles)
        self.graphTempPos.setLabel("bottom", "Position (cm)", **styles)
        self.graphTempPos.showGrid(x=True, y=True)

        self.temp_h_box = QHBoxLayout()

        self.instant_temp_button = QPushButton(self)
        self.instant_temp_button.setText("🤒")
        self.instant_temp_button.pressed.connect(self.getT)
        self.temp_h_box.addWidget(self.instant_temp_button)

        self.instant_temp_label = QLabel("")
        self.instant_temp_label.setText("Read Temperature")
        self.instant_temp_label.setFont(QFont('Munhwa Gothic', 20))
        self.temp_h_box.addWidget(self.instant_temp_label)

        self.profile_temp_button = QPushButton(self)
        self.profile_temp_button.setText("🤒📈")
        self.profile_temp_button.pressed.connect(self.collect_temp_profile)
        self.temp_h_box.addWidget(self.profile_temp_button)

        self.temp_h_group_box = QGroupBox()
        self.temp_h_group_box.setLayout(self.temp_h_box)


        # add widgets to vertical box layout
        vbox = QVBoxLayout()
        vbox.addWidget(self.h_controller_check)
        vbox.addWidget(self.h_power)
        vbox.addWidget(self.vac)

        vbox.addWidget(self.graphTempPos)
        vbox.addWidget(self.temp_h_group_box)

        # set alignment, spacing, and assign layout to groupBox
        vbox.setAlignment(Qt.AlignmentFlag.AlignTop)
        vbox.setSpacing(10)
        groupBox.setLayout(vbox)
        return groupBox

    def getT(self):
        logT = threading.Thread(target=tempLog, args=(1, 100, False))
        logT.start()
        logT.join()
        global current_probe_temp
        self.instant_temp_label.setText("%4.2f°C" % (current_probe_temp))


    def collect_temp_profile(self):
        self.graphTempPos.clear()
        plungeTemp.clear()
        plunge_temp_time.clear()

        self.graphTempPos.setTitle("Plunge Cooler Temperature vs Position", color="w", size="10pt")
        styles = {"color": "white", "font-size": "10px"}
        self.graphTempPos.setLabel("left", "Voltage (V)", **styles)
        self.graphTempPos.setLabel("bottom", "Position (cm)", **styles)
        print("Nudging down specified amount in 'nudge' to collect profile....")
        epos.VCS_SetEnableState(keyHandle, nodeID, byref(pErrorCode))  # disable device

        # create storage variables (Py arrays) for data
        testSet = []
        testPos = []
        value_n = (-1 * (get_position() * leadscrew_inc / encoder_pulse_num)) + self.nudge_spinbox.value()  # approximate updated position
        x = 0
        while (x < 200):
            read_temperature()
            testSet.append(val)
            testPos.append(timer())
            x = x + 1
            value_n = (-1 * ( get_position() * leadscrew_inc / encoder_pulse_num)) + self.nudge_spinbox.value()  # approximate updated position
        print(testSet)
        move_nudge("down", self.nudge_spinbox.value())  # calculate nudge value from input & move
        value_n = (-1 * (
                get_position() * leadscrew_inc / encoder_pulse_num)) + self.nudge_spinbox.value()  # approximate updated position
        # time.sleep(0.1)
        self.current_pos_label.setText("%4.2f cm" % (value_n))  # update position label
        self.graphTempPos.plot(testPos, testSet)

    # function: guiheater_controller
    # purpose: turns on or off heater controller depending on checkbox status
    # parameters: self
    # return: none
    def guiheater_controller(self):
        if self.h_controller_check.isChecked() == False:
            self.h_power.setChecked(False)
        ni_set('heater_controller', self.h_controller_check.isChecked())

    # function: guiheater_power
    # purpose: turn heater on or off depending on checkbox status; will not turn on without controller being on
    # parameters: self
    # return: none
    def guiheater_power(self):
        if self.h_power.isChecked():
            self.h_controller_check.setChecked(True)
        ni_set('heater', self.h_power.isChecked())

    # function: guivacuum
    # purpose: turn vacuum on or off depending on checkbox status
    # parameters: self
    # return: none
    def guivacuum(self):
        ni_set('vacuum',  (not self.vac.isChecked()))

    # function: plungevac_on
    # purpose: enables or disables spinbox input into time input; enables or disables continuous vacuum
    # parameters: self
    # return: none
    def plungevac_on(self):
        self.vac_on_time.setEnabled(self.plungevac.isChecked())
        self.vac.setDisabled(self.plungevac.isChecked())
        self.vac.setChecked(False)

    # function: plungepause_on
    # purpose: enables or disables spinbox input into time and distance inputs
    # parameters: self
    # return: none
    def plungepause_on(self):
        self.plungepausedist.setEnabled(self.plungepause.isChecked())
        self.pp_time_box.setEnabled(self.plungepause.isChecked())

    # endregion setup_funcs2

    # region setup_funcs2

    # function: setupBox
    # purpose: create widgets for plunge settings/control options
    # parameters: self
    # return: GroupBox
    def setupBox2(self):
        groupBox = QGroupBox("Vacuum Controls")  # create a GroupBox

        # create label and spinbox for plunge vac time - allows for vacuum to turn on prior to plunge
        self.plungevaclabel = QLabel(self)
        self.plungevaclabel.setText(
            "Toggle PLUNGE VAC and set time to run vacuum before plunge. Note: DOESN'T add to P-P-P time")
        self.plungevaclabel.setWordWrap(True)
        self.plungevaclabel.setFont(QFont('Munhwa Gothic', 20))
        self.plungevac = QCheckBox(self)
        self.plungevac.setText("PLUNGE VAC")
        self.plungevac.setFont(QFont('Munhwa Gothic', 20))
        self.plungevac.setStyleSheet("QCheckBox::indicator"
                                     "{"
                                     "width : 70px;"
                                     "height : 70px;"
                                     "}")

        # create spinbox for time to pause with vacuum on
        self.vac_on_time = QDoubleSpinBox(self)
        self.vac_on_time.setMinimum(0)
        self.vac_on_time.setMaximum(10)
        self.vac_on_time.setSuffix(" s")
        self.vac_on_time.setSingleStep(0.5)
        self.vac_on_time.setFont(QFont('Munhwa Gothic', 20))

        # create label to explain p-p-p
        self.plungepauselabel = QLabel(self)
        self.plungepauselabel.setText("Toggle PLUNGE PAUSE and set time & dist to plunge")
        self.plungepauselabel.setWordWrap(True)
        self.plungepauselabel.setFont(QFont('Munhwa Gothic', 20))
        self.plungepause = QCheckBox(self)
        self.plungepause.setText("PLUNGE PAUSE PLUNGE")
        self.plungepause.setFont(QFont('Munhwa Gothic', 20))
        self.plungepause.setStyleSheet("QCheckBox::indicator"
                                       "{"
                                       "width : 70px;"
                                       "height : 70px;"
                                       "}")

        # create spinbox for distance to move for p-p-p during pause stage
        self.plungepausedist = QDoubleSpinBox(self)
        self.plungepausedist.setMinimum(0.5)
        self.plungepausedist.setMaximum(25)
        self.plungepausedist.setSuffix(" cm")
        self.plungepausedist.setSingleStep(0.5)
        self.plungepausedist.setFont(QFont('Munhwa Gothic', 20))

        # create spinbox to read in time to pause in p-p-p
        self.pp_time_box = QDoubleSpinBox(self)
        self.pp_time_box.setMinimum(0)
        self.pp_time_box.setSuffix(" s")
        self.pp_time_box.setSingleStep(0.5)
        self.pp_time_box.setFont(QFont('Munhwa Gothic', 20))

        # connect checkboxes to functions - update when checkbox value is changed
        self.plungevac.stateChanged.connect(self.plungevac_on)
        self.plungevac.stateChanged.connect(self.plungevac_on)
        self.plungepause.stateChanged.connect(self.plungepause_on)

        # set enable state of checkboxes
        self.plungevac.setEnabled(True)
        self.vac_on_time.setEnabled(False)
        self.plungepause.setEnabled(True)
        self.plungepausedist.setEnabled(False)
        self.pp_time_box.setEnabled(False)

        # add widgets to vertical box layout
        vbox = QVBoxLayout()
        vbox.addWidget(self.plungevaclabel)
        vbox.addWidget(self.plungevac)
        vbox.addWidget(self.vac_on_time)
        vbox.addWidget(self.plungepauselabel)
        vbox.addWidget(self.plungepause)
        vbox.addWidget(self.plungepausedist)
        vbox.addWidget(self.pp_time_box)

        # set alignment, spacing, and assign layout to groupBox
        vbox.setAlignment(Qt.AlignmentFlag.AlignTop)
        vbox.setSpacing(10)
        groupBox.setLayout(vbox)
        return groupBox

    # endregion setup_funcs2

    def graphBox(self):

        groupBox = QGroupBox("Graphs")  # create a GroupBox

        # create graph widget to read velocity; updates in plunge stage
        self.graphVel = pg.PlotWidget(self)
        self.graphVel.setBackground('black')
        self.graphVel.setTitle("Plunge Cooler Velocity vs Time", color="w", size="10pt")
        styles = {"color": "white", "font-size": "10px"}
        self.graphVel.setLabel("left", "Velocity (m/s)", **styles)
        self.graphVel.setLabel("bottom", "Time (s)", **styles)
        self.graphVel.showGrid(x=True, y=True)
        self.graphVel.setXRange(0.3, 0)
        self.graphVel.setYRange(2.2, 0)

        # create graph widget to read velocity; updates in plunge stage
        self.graphVelPos = pg.PlotWidget(self)
        self.graphVelPos.setBackground('black')
        self.graphVelPos.setTitle("Plunge Cooler Velocity vs Position", color="w", size="10pt")
        styles = {"color": "white", "font-size": "10px"}
        self.graphVelPos.setLabel("left", "Velocity (m/s)", **styles)
        self.graphVelPos.setLabel("bottom", "Position (cm)", **styles)
        self.graphVelPos.showGrid(x=True, y=True)
        self.graphVelPos.setXRange(23, 0)
        self.graphVelPos.setYRange(2.2, 0)

        vbox = QHBoxLayout()
        vbox.setAlignment(Qt.AlignmentFlag.AlignTop)
        vbox.setSpacing(10)
        vbox.addWidget(self.graphVel)
        vbox.addWidget(self.graphVelPos)
        groupBox.setLayout(vbox)
        return groupBox

    def contextMenuEvent(self, e):
        context = QMenu(self)
        act1 = QAction('Stop Process')
        act1.setFont(QFont('Munhwa Gothic', 40))
        act3 = QAction('(:')

        context.addAction(act1)
        context.addAction(act3)

        act1.triggered.connect(self.exitFunction)
        context.exec(e.globalPos())

    def exitFunction(self):
        print("Force exiting application")
        ni_set('vacuum',            True)
        ni_set('heater',            True)
        ni_set('heater_controller', False)
        ni_set('light',             False)
        close_device(keyHandle)
        QApplication.closeAllWindows()
        sys.exit(0)


# function: start_app
# purpose: begins application and sets darkmode settings
# parameters: none
# return: none
def start_app():
    # create instance of application - only one needed per application
    app = QApplication(sys.argv)  # Passing in Python list (sys.argv) with command line arguments
    qdarktheme.setup_theme()
    # can pass in empty list [] if command line arguments will not be used to control Qt

    # create Qt widget - window
    # all top-level widgets are windows -> if it isn't a child widget, or nested
    startWindow = MainWindow()
    startWindow.show()  # show the window - these are hidden by default
    exitCode = app.exec()

    # when closed properly via x settings, reset all components that may have been on
    ni_set('vacuum', True)
    ni_set('heater', True)
    ni_set('heater_controller', False)
    ni_set('light', False)
    close_device(keyHandle)


"""
NI INSTRUMENT COMMUNICATION COMMANDS - HEATER, GAS EXCHANGE, LIGHT
"""

# region serial_comms
def brake_set(state):
    if state:
        ser.write(b'5') # brake
    else:
        ser.write(b'4') # release
    resp = ser.read(3)
    return (resp == ACK)

# endregion serial_comms


# region NI_instruments


# general function for toggling any digital out line on the ni daq
def ni_set(device, value):
    with nidaqmx.Task() as task:
        task.do_channels.add_do_chan(PINOUT[device])
        task.start()
        print(device + " set to " + str(value))
        task.write(value)
        #time.sleep(.5)
        task.stop()

def A_move(dir, steps):
    moveT = threading.Thread(target=A_move_thread, args=(dir, steps))
    moveT.start()

def A_move_thread(dir, steps):
    ni_set('A_motor_power', True)
    ni_set('A_dir', dir)
    with nidaqmx.Task() as step_task:
        step_task.do_channels.add_do_chan(PINOUT['A_step'])
        step_task.start()
        for i in range(steps):
            step_task.write(True)
            time.sleep(A_SPEED)
            step_task.write(False)
            time.sleep(A_SPEED)
        step_task.stop()
    ni_set('A_motor_power', False)
def read_temperature():
    # reads voltages into a global array
    with nidaqmx.Task() as tempTask:
        sampling_rate = 2000000  # can alter sampling rate for quicker time points depending on DAQ max reads
        try:
            tempTask.ai_channels.add_ai_voltage_chan(PINOUT['temperature'])
            # sets sample rate, clock source "" sets to internal clock
            tempTask.timing.cfg_samp_clk_timing(sampling_rate, source="", active_edge=nidaqmx.constants.Edge.RISING)
            global val
            val = tempTask.read()
            plungeTemp.append(val)
            plunge_temp_time.append(timer() - temp_timer)
        finally:
            return


# endregion NI_instruments

"""
MAXON MOTOR COMMANDS - USES EPOS COMMAND LIBRARY IMPORTED FROM .DLL FILE
"""


# region maxon_motor

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




def dataLogThread():
    startTime = timer()
    global plunge_done_flag
    plunge_done_flag = False
    i=0
    while True:
        # record data
        true_velocity = get_velocity()
        true_posCM = get_position()
        plungeTime.append(timer() - startTime)
        #plungeData.append(-1*true_velocity)
        plungeData.append((-1) * true_velocity * leadscrew_inc / 100 / 60)
        plungePosData.append((-1 * (true_posCM * leadscrew_inc / encoder_pulse_num)))
        if plunge_done_flag:
            i += 1
            if i == 50: #COLLECT EXTRA POINTS TO CAPPOUTRE DECELERATION
                break

    print("writing data to file")
    filename = "C:\\Users\\ret-admin\\Desktop\\plunge_data\\plunge\\"
    filename += datetime.datetime.now().strftime("%m-%d-%Y.%H-%M-%S")
    f = open(filename + '.txt', 'w')
    for i in range(len(plungeTime)):
        f.write(str(plungeTime[i]) + ',' + str(plungePosData[i]) + ',' +  str(plungeData[i]) + '\n')
    f.close()


def printThread():
    while not plunge_done_flag:
        print(get_position())

# function: move_plunge
# purpose: plunges the carriage downwards rapidly (can set speed and "position"; set to large -ve if plunging full
# parameters: int, int
# return: none
def move_plunge():
    if LEO_MODE:
        global PID_P, PID_I
        global plunge_done_flag
        # stop_position = -27500
        stop_position = 15000
        ''' timepoint pos is actually a function of timepoint in ms '''
        timepoint_position = 10000
        plunge_speed = -8000
        plunge_timeout = 3

        msg = '2' + str(stop_position) + ('0' if timepoint_position < 10000 else '') + str(timepoint_position)
        ser.write(bytes(msg, 'utf-8'))
        if ser.read() != ACK:
            return
        # test
        # logT = threading.Thread(target=dataLogThread)
        # logT.start()
        #printT = threading.Thread(target=printThread)
         #printT.start()
        if readTemp_flag:
            tempT = threading.Thread(target=tempLog)
            tempT.start()
        PID_P = 4000
        PID_I = 1
        epos.VCS_SetVelocityRegulatorGain(keyHandle, nodeID, PID_P, PID_I, byref(pErrorCode))
#        epos.VCS_SetMaxAcceleration(keyHandle, nodeID, 4294967295, byref(pErrorCode))
#        epos.VCS_ActivateVelocityMode(keyHandle, nodeID, byref(pErrorCode))
#        epos.VCS_SetVelocityMust(keyHandle, nodeID, plunge_speed, byref(pErrorCode))

        epos.VCS_ActivateProfileVelocityMode(keyHandle, nodeID, byref(pErrorCode))
        epos.VCS_SetVelocityProfile(keyHandle, nodeID, 4294967295, 4294967295, byref(pErrorCode))
        epos.VCS_MoveWithVelocity(keyHandle, nodeID, plunge_speed, byref(pErrorCode))
        start_time = timer()

        ser.read()
        posLog = []
        i = 0
        while True:
            log = ser.read()
            print(log)
            if log == ACK:
                break
            else:
                poslog[i] = log
                i += 1
        print(posLog)

        epos.VCS_SetQuickStopState(keyHandle, nodeID, byref(pErrorCode))

        plunge_done_flag = True
        logT.join()
        A_move(A_UP, 3500)
        if readTemp_flag:
            tempT.join()
        print("regained log thread")
        # printT.join()
        # print("regained print thread")





# captures the next 5 seconds of temp data
def tempLog(sample_seconds=5, sampling_rate=20000, log=True):
    with nidaqmx.Task() as tempTask:
        num_samples = sampling_rate * sample_seconds
        tempTask.ai_channels.add_ai_voltage_chan(PINOUT['thermocouple'])
        # sets sample rate, clock source "" sets to internal clock
        tempTask.timing.cfg_samp_clk_timing(sampling_rate, source="", active_edge=nidaqmx.constants.Edge.RISING,
                                            sample_mode=nidaqmx.constants.AcquisitionType.FINITE,
                                            samps_per_chan=num_samples)

        print("done collecting T")
        temps = tempTask.read(number_of_samples_per_channel=num_samples)
        if log:
            filename = "C:\\Users\\ret-admin\\Desktop\\plunge_data\\temp\\"
            filename += datetime.datetime.now().strftime("%m-%d-%Y.%H-%M-%S")
            f = open(filename + '.txt', 'w')
            for temp in temps:
                f.write(str(temp) + '\n')
            f.close()
        else:
            global current_probe_temp
            current_probe_temp = (sum(temps) / len(temps))
        print("regained temperature thread")
        tempTask.stop()




def clear_errors(key):
    p3 = epos.VCS_ClearFault(key, nodeID, byref(pErrorCode))  # clear all faults
    p5 = epos.VCS_SetEnableState(key, nodeID, byref(pErrorCode))  # disable device


# function: move_nudge
# purpose: nudges the carriage upwards or downwards
# parameters: string, int
# return: none
def move_nudge(direction, nudge_step):
    target_speed = 600
    pCurrent = c_short()
    nudge_step = int(nudge_step / leadscrew_inc * encoder_pulse_num)

    if direction == "down":
        nudge_step *= -1

    nudge_step = nudge_step + get_position()

    # TODO: MAKE SURE IT DOESNT GO OUT OF BOUNDS

    print("at: " + str(get_position()) + "; moving to: " + str(nudge_step))
    epos.VCS_ActivateProfilePositionMode(keyHandle, nodeID, byref(pErrorCode))
    epos.VCS_SetPositionProfile(keyHandle, nodeID, target_speed, acceleration, deceleration, byref(pErrorCode))  # set profile parameters
    epos.VCS_HaltPositionMovement(keyHandle, nodeID, byref(pErrorCode))
    time.sleep(.1)
    brake_set(False)
    epos.VCS_MoveToPosition(keyHandle, nodeID, nudge_step, True, True, byref(pErrorCode))  # move to position
    time.sleep(.5)
    #while True:
    #    epos.VCS_GetCurrentIs(keyHandle, nodeID, byref(pCurrent), byref(pErrorCode))
    #    print(pCurrent.value)
    #    if pCurrent.value <= 400:  # not mving
    #        break
    brake_set(True)



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
    # move_home()
    # a = c_long()
    # b = c_long()
    # c = c_long()
    # epos.VCS_GetDcMotorParameter(keyHandle, nodeID, byref(a), byref(b), byref(c), byref(pErrorCode))

    # print(str(a.value) + ", " + str(b.value) + ", " + str(c.value) + ", ")
    epos.VCS_SetDcMotorParameter(keyHandle, nodeID, 6000, 10000, 48)

    return [p1, p2, p3, p4, p5]


# function: close_device
# purpose: closes maxon controller & ends program
# parameters: none
# return: none
def close_device(key):
    epos.VCS_SetDisableState(keyHandle, nodeID, byref(pErrorCode))  # disable device
    epos.VCS_CloseDevice(keyHandle, byref(pErrorCode))  # close device
    print("Device closed")
    QApplication.closeAllWindows()
    sys.exit(0)


# endregion maxon_motor

# main func
if __name__ == '__main__':
    ser = serial.Serial('/dev/ttyUSB0', 115200)  # open serial port
    ser.write(b'Z')  # write a string

    print("******************************************************************************************************")
    print("Initializing MAXON interface, will exit if failed")
    print("xd")

    keyHandle = epos.VCS_OpenDevice(b'EPOS2', b'MAXON SERIAL V2', b'USB', b'USB0',
                                    byref(pErrorCode))  # specify EPOS version and interface

    if int(keyHandle) == 0:
        print("keyHandle failed!")

    # initialize device (MAXON)
    x = initialize_device(keyHandle)

    if x[0] == 0 or x[1] == 0 or x[2] == 0 or x[3] == 0 or x[4] == 0:  # check for initialization failures
        print("Setup failed. Exiting program.")
        close_device(keyHandle)
    else:
        print("Starting application...")
        start_app()
        close_device(keyHandle)
        QApplication.closeAllWindows()
        sys.exit(0)
