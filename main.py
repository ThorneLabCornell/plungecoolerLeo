"""
AUTHOR: KASHFIA (ASH) MAHMOOD
DATE: 06/14/2023
ACKNOWLEDGEMENTS: John Allen Indergaard for his sacrifices & Matt for his GUI praise
"""
# import all necessary libraries
# region imports_and_constants

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
pVelIs = c_uint()

# Defining a variable NodeID and configuring connection
nodeID = 1  # set to 2; need to change depending on how the maxon controller is set up (check EPOS Studio)
baudrate = 1000000
timeout = 500

# Configure desired motion profile
# acceleration should be 2g: 2*9.81m/s^2 -> 190 000
acceleration = 80000  # rpm/s, up to 1e7 would be possible, 98 100 is 2g
deceleration = 300000  # rpm/s

EXIT_CODE_REBOOT = -12345
device_num = "Dev1"

# global data collection
plungeTime = []
plungeData = []
plungeTemp = []
plungePosData = []
prevPosData = 0
homePosDataPrev = 0
temp_timer = timer()
ultimate_timer = timer()
plunge_temp_time = []
pos_home_raw = 38000
pos_home = 0
read_time = True
val = 0  # temporary temperature storage
leadscrew_inc = 1.2
encoder_pulse_num = 512 * 4

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
        self.tabs.addTab(self.tab1, 'Plunge')

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
        global pos_home_raw
        light(True)  # turn on the light to signify movement
        homePosData = 0
        clear_errors(keyHandle)  # after movement faults, reset by re-initializing device
        if (self.tabs.currentIndex()) == 0:
            epos.VCS_SetEnableState(keyHandle, nodeID, byref(pErrorCode))  # enable device
            epos.VCS_ActivateProfilePositionMode(keyHandle, nodeID, byref(pErrorCode))
            move_home()  # start movement
            clear_errors(keyHandle)  # after movement faults, reset by re-initializing device
        light(False)  # turn light off to signify no movement
        home = 0  # manually set home position to be 0
        # print(get_position())  # print to console the actual current reading of position
        pos_home = (get_position() - pos_home_raw) * leadscrew_inc / encoder_pulse_num
        self.current_pos_label.setText("%4.2f cm" % pos_home)

    # function: plungeBegin
    # purpose: runs the plunge cooler down at 19000 rpm (2 m/s) until the device faults and hits the hard stop
    # parameters: self
    # return: none
    def plungeBegin(self):
        homePosDataPrev = 0
        global pos_home_raw
        light(True)  # turn light on to show movement
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
                vacuum(True)  # turn on vacuum
                while True:  # hold loop until time is reached, then plunge
                    if timer() - start >= wait_time - pp_wait_time:
                        break
                self.vac_on_time.setEnabled(True)  # return previous settings to enable changes
                self.plungevac.setEnabled(True)

            move_nudge('down', self.plungepausedist.value())  # move to the distance

            if self.plungevac.isChecked() and self.vac_on_time.value() == pp_wait_time:
                vacuum(True)
            pptimer = timer()  # start timer for plunge pause plunge

            vac_on = False
            while True:  # hold in loop until pause time has been reached, then proceed to plunging stage
                if self.plungevac.isChecked() and ~vac_on and self.vac_on_time.value() < pp_wait_time and (
                        timer() - pptimer > self.vac_on_time.value()):
                    vacuum(True)
                    vac_on = True
                if timer() - pptimer > pp_wait_time:
                    break

            move_plunge()  # arbitrary amount to ensure fault state reached; -ve is down
            vacuum(False)

        elif self.plungevac.isChecked():  # vacuum time; note that this does not add to the p-p-p time
            self.vac_on_time.setEnabled(False)
            self.plungevac.setEnabled(False)  # any conflicting settings are off or set settings are kept constant
            wait_time = self.vac_on_time.value()  # read time to wait; turns on vacuum and pauses before plunge
            start = timer()
            vacuum(True)  # turn on vacuum
            while True:  # hold loop until time is reached, then plunge
                if timer() - start >= wait_time or timer() - pptimer >= wait_time:
                    epos.VCS_SetEnableState(keyHandle, nodeID, byref(pErrorCode))  # disable device
                    move_plunge()  # arbitrary amount to ensure fault state reached; -ve is down
                    break
            vacuum(False)  # turn off vacuum following plunge
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

        light(False)  # turn off light
        value_n = (-1 * (get_position()-pos_home_raw) * leadscrew_inc / encoder_pulse_num)  # approximate updated position
        self.current_pos_label.setText("%4.2f cm" % (value_n))  # update label with position
        self.graphVel.plot(plungeTime, plungeData)  # plot collected data
        self.graphVelPos.plot(plungePosData,
                              plungeData)  # plot vel vs pos -- seet to plungePosData vs plungeData v vs pos

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
        self.upNudge.setAutoRepeat(True)
        self.upNudge.setEnabled(False)
        self.upNudge.setCheckable(True)
        self.downNudge.setAutoRepeat(True)
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
        # light(True)  # turn on light to indicate movement stage
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
        global pos_home_raw
        epos.VCS_ActivateProfilePositionMode(keyHandle, nodeID, byref(pErrorCode))

        move_nudge("up", self.nudge_spinbox.value())  # call function to move by nudge distance
        value_n = (-1 * (get_position()-pos_home_raw) * leadscrew_inc / encoder_pulse_num) + self.nudge_spinbox.value() # approximate updated position
        self.current_pos_label.setText("%4.2f cm" % (value_n))  # update label with position

    # function: stopNudge
    # purpose: stops nudge function
    # parameters: self
    # return: none
    def stopNudge(self):
        # reset settings to enable plunging and disable nudging
        light(False)
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
        global pos_home_raw
        epos.VCS_ActivateProfilePositionMode(keyHandle, nodeID, byref(pErrorCode))
        print(int(self.nudge_spinbox.value() / leadscrew_inc * encoder_pulse_num))
        move_nudge("down", self.nudge_spinbox.value())  # calculate nudge value from input & move

        value_n = (-1 * (get_position()-pos_home_raw) * leadscrew_inc / encoder_pulse_num) + self.nudge_spinbox.value()  # approximate updated position

        self.current_pos_label.setText("%4.2f cm" % (value_n))  # update position label

    # endregion nudgeBox_and_func

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

        self.tempButton = QPushButton(self)
        self.tempButton.setText("Take Temperature Measurement")
        self.tempButton.pressed.connect(self.collect_temp_profile)

        # create graph widget to read temperature; updates in plunge stage
        self.graphTempPos = pg.PlotWidget(self)
        self.graphTempPos.setBackground('black')
        self.graphTempPos.setTitle("Plunge Cooler Temperature vs Position", color="w", size="10pt")
        styles = {"color": "white", "font-size": "10px"}
        self.graphTempPos.setLabel("left", "Voltage (V)", **styles)
        self.graphTempPos.setLabel("bottom", "Position (cm)", **styles)
        self.graphTempPos.showGrid(x=True, y=True)

        self.clear_temp_button = QPushButton(self)
        self.clear_temp_button.setText("Clear Temperature Measurements")
        self.clear_temp_button.pressed.connect(self.clear_temp)

        # add widgets to vertical box layout
        vbox = QVBoxLayout()
        vbox.addWidget(self.h_controller_check)
        vbox.addWidget(self.h_power)
        vbox.addWidget(self.vac)
        vbox.addWidget(self.tempButton)
        vbox.addWidget(self.graphTempPos)
        vbox.addWidget(self.clear_temp_button)

        # set alignment, spacing, and assign layout to groupBox
        vbox.setAlignment(Qt.AlignmentFlag.AlignTop)
        vbox.setSpacing(10)
        groupBox.setLayout(vbox)
        return groupBox

    def clear_temp(self):
        self.graphTempPos.clear()
        plungeTemp.clear()
        plunge_temp_time.clear()

    def collect_temp_profile(self):
        self.graphTempPos.setTitle("Plunge Cooler Temperature vs Position", color="w", size="10pt")
        styles = {"color": "white", "font-size": "10px"}
        self.graphTempPos.setLabel("left", "Voltage (V)", **styles)
        self.graphTempPos.setLabel("bottom", "Position (cm)", **styles)
        print("Nudging down specified amount in 'nudge' to collect profile....")
        epos.VCS_SetEnableState(keyHandle, nodeID, byref(pErrorCode))  # disable device

        # create storage variables (Py arrays) for data
        testSet = []
        testPos = []
        value_n = (-1 * (
                get_position() * leadscrew_inc / encoder_pulse_num)) + self.nudge_spinbox.value()  # approximate updated position
        x = 0
        while (x < 20):
            read_temperature()
            testSet.append(val)
            testPos.append(value_n)
            x = x + 1
            value_n = (-1 * (
                    get_position() * leadscrew_inc / encoder_pulse_num)) + self.nudge_spinbox.value()  # approximate updated position

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
        heater_controller(self.h_controller_check.isChecked())

    # function: guiheater_power
    # purpose: turn heater on or off depending on checkbox status; will not turn on without controller being on
    # parameters: self
    # return: none
    def guiheater_power(self):
        if self.h_power.isChecked():
            self.h_controller_check.setChecked(True)
        heater(self.h_power.isChecked())

    # function: guivacuum
    # purpose: turn vacuum on or off depending on checkbox status
    # parameters: self
    # return: none
    def guivacuum(self):
        vacuum(self.vac.isChecked())

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
        vacuum(False)
        heater(False)
        heater_controller(False)
        light(False)
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
    vacuum(False)
    heater(False)
    heater_controller(False)
    light(False)
    close_device(keyHandle)


"""
NI INSTRUMENT COMMUNICATION COMMANDS - HEATER, GAS EXCHANGE, LIGHT
"""


# region NI_instruments

# function: heater_controller
# purpose: turns heater controller on or off
# parameters: bool
# return: none
def heater_controller(value):
    # heater controller is connected to port 0
    with nidaqmx.Task() as heater_task:
        heater_task.do_channels.add_do_chan(device_num + "/port0/line6")
        heater_task.write(value)
        heater_task.stop()


# function: heater
# purpose: turns heater on or off
# parameters: bool
# return: none
def heater(value):
    # heater is connected to port 4
    with nidaqmx.Task() as heater_task:
        heater_task.do_channels.add_do_chan(device_num + "/port0/line3")
        heater_task.write(value)
        heater_task.stop()


# function: vacuum
# purpose: turns heater on or off
# parameters: bool
# return: none
def vacuum(value):
    # vacuum DC power is connected to port 1
    with nidaqmx.Task() as vac_task:
        vac_task.do_channels.add_do_chan(device_num + "/port0/line2")
        vac_task.write(value)
        vac_task.stop()


# function: light
# purpose: turns light on or off
# parameters: bool
# return: none
def light(value):
    # light is connected to port 3
    # with nidaqmx.Task() as light_task:  # write to NI DAQ
    #     light_task.do_channels.add_do_chan(device_num + "/port0/line3")
    #     light_task.write(value)
    #     light_task.stop()
    print("")


def read_temperature():
    # reads voltages into a global array
    with nidaqmx.Task() as tempTask:
        sampling_rate = 2000000  # can alter sampling rate for quicker time points depending on DAQ max reads
        try:
            tempTask.ai_channels.add_ai_voltage_chan(device_num + "/ai10")
            tempTask.timing.cfg_samp_clk_timing(sampling_rate, source="",
                                                active_edge=nidaqmx.constants.Edge.RISING)
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


# function: move_plunge
# purpose: plunges the carriage downwards rapidly (can set speed and "position"; set to large -ve if plunging full
# parameters: int, int
# return: none
def move_plunge():
    global homePosDataPrev
    global pos_home_raw
    true_position = get_position()
    target_position = 1300
    if round(abs(true_position), -2) == round(pos_home_raw, -2):
        target_position = 1300  # 1300 is lowest without p-p-p from home
    else:
        target_position = int(target_position - 300 * (get_position() - pos_home_raw) * leadscrew_inc / encoder_pulse_num)
    print (target_position)
    target_speed = 9500
    startTime = timer()
    epos.VCS_ActivateProfilePositionMode(keyHandle, nodeID, byref(pErrorCode))
    # while true, keep attempting to plunge - while loop may not be needed, as it is usually desired for precision

    while True:
        if target_speed != 0:
            # set profile & begin move
            passProf = epos.VCS_SetPositionProfile(keyHandle, nodeID, target_speed, acceleration, deceleration,
                                                   byref(pErrorCode))  # set profile parameters
            passMove = epos.VCS_MoveToPosition(keyHandle, nodeID, target_position, True, True,
                                               byref(pErrorCode))  # move to position

        elif target_speed == 0:  # stop movement
            epos.VCS_HaltPositionMovement(keyHandle, nodeID, byref(pErrorCode))  # halt motor

        # record data
        true_velocity = get_velocity()
        true_posCM = get_position()
        plungeTime.append(timer() - startTime)
        plungeData.append((-1) * true_velocity * leadscrew_inc / 100 / 60)
        plungePosData.append((-1 * ((get_position() - pos_home_raw) * leadscrew_inc / encoder_pulse_num)))

        # lock = threading.Lock()
        # lock.acquire()
        # tempthread = threading.Thread(target=read_temperature, args=())
        # tempthread.start()
        # # tempthread.join()

        pIsInFault = c_uint()
        temp0 = epos.VCS_GetFaultState(keyHandle, nodeID, byref(pIsInFault), byref(pErrorCode))
        if pIsInFault.value != 0:  # timeout/break options
            epos.VCS_HaltPositionMovement(keyHandle, nodeID, byref(pErrorCode))  # halt motor
            break
        true_position = get_position()
        if round(abs(true_position - target_position), -2) < 100 or timer() - startTime > 0.5:
            epos.VCS_HaltPositionMovement(keyHandle, nodeID, byref(pErrorCode))  # halt motor
            break

        homePosDataPrev = get_position()


# function: move_home
# purpose: move carriage upwards until faults
# parameters: none
# return: none
def move_home():
    global homePosDataPrev
    global pos_home_raw
    target_position = pos_home_raw
    target_speed = 500
    startTime = timer()
    epos.VCS_ActivateProfilePositionMode(keyHandle, nodeID, byref(pErrorCode))
    while True:
        print(get_position())
        if target_speed != 0 and pos_home_raw != get_position():
            passProf = epos.VCS_SetPositionProfile(keyHandle, nodeID, target_speed, acceleration, deceleration,
                                                   byref(pErrorCode))  # set profile parameters
            passMove = epos.VCS_MoveToPosition(keyHandle, nodeID, target_position, True, True,
                                               byref(pErrorCode))  # move to position

        elif target_speed == 0:
            epos.VCS_HaltPositionMovement(keyHandle, nodeID, byref(pErrorCode))  # halt motor
            break
        pIsInFault = c_uint()
        temp0 = epos.VCS_GetFaultState(keyHandle, nodeID, byref(pIsInFault), byref(pErrorCode))

        if 4 > abs(get_position() - homePosDataPrev) >= 0 and (abs(target_position - get_position()) < 200):
            epos.VCS_HaltPositionMovement(keyHandle, nodeID, byref(pErrorCode))  # halt motor
            pos_home_raw = get_position()
            break
        homePosDataPrev = get_position()


def clear_errors(key):
    p3 = epos.VCS_ClearFault(key, nodeID, byref(pErrorCode))  # clear all faults
    p5 = epos.VCS_SetEnableState(key, nodeID, byref(pErrorCode))  # disable device


# function: move_nudge
# purpose: nudges the carriage upwards or downwards
# parameters: string, int
# return: none
def move_nudge(direction, nudge_step):
    nudge_step = int(nudge_step / leadscrew_inc * encoder_pulse_num)
    epos.VCS_ActivateProfilePositionMode(keyHandle, nodeID, byref(pErrorCode))
    target_speed = 500
    if direction == "up":
        nudge = nudge_step
    else:  # downward movement
        nudge = nudge_step * -1
    nudge = nudge + abs(get_position())

    if target_speed != 0:
        if nudge > pos_home_raw:
            nudge = pos_home_raw
        if nudge <= 0:
             nudge = 0
        passProf = epos.VCS_SetPositionProfile(keyHandle, nodeID, target_speed, acceleration, deceleration,
                                               byref(pErrorCode))  # set profile parameters
        passMove = epos.VCS_MoveToPosition(keyHandle, nodeID, nudge, True, True,
                                           byref(pErrorCode))  # move to position


def move_home_sensor():
    time.sleep(5)
    epos.VCS_FindHome(keyHandle, nodeID, 7, byref(pErrorCode))


# function: move_general
# purpose: moves the carriage to a specified position
# parameters: int, int
# return: none
def move_general(target_position, target_speed):
    global pos_home_raw
    target_position = pos_home_raw - target_position
    print(target_position)

    while True:
        if target_speed != 0:
            passProf = epos.VCS_SetPositionProfile(keyHandle, nodeID, target_speed, acceleration, deceleration,
                                                   byref(pErrorCode))  # set profile parameters
            passMove = epos.VCS_MoveToPosition(keyHandle, nodeID, target_position, True, True,
                                               byref(pErrorCode))  # move to position

        elif target_speed == 0:
            epos.VCS_HaltPositionMovement(keyHandle, nodeID, byref(pErrorCode))  # halt motor
        true_position = get_position()
        print(true_position)
        if round(true_position, -2) <= target_position:
            break


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
    p2 = epos.VCS_SetProtocolStackSettings(key, baudrate, timeout, byref(pErrorCode))  # set baudrate
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

    epos.VCS_SetMaxFollowingError(key, nodeID, 5000, byref(pErrorCode))
    # move_home()
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
