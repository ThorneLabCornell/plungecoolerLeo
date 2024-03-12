# GUI imports
from PyQt6.QtCore import *
from PyQt6.QtGui import *
from PyQt6.QtWidgets import *
import motor
import sys
import pyqtgraph as pg
import qdarktheme
from timeit import default_timer as timer
import threading

import globals as globs
import ni
import stm
import A_axis


def begin():
    # create instance of application - only one needed per application
    app = QApplication(sys.argv)  # Passing in Python list (sys.argv) with command line arguments
    qdarktheme.setup_theme()
    # can pass in empty list [] if command line arguments will not be used to control Qt

    # create Qt widget - window
    # all top-level widgets are windows -> if it isn't a child widget, or nested
    globs.gui= MainWindow()
    globs.gui.show()  # show the window - these are hidden by default
    app.exec()


# I'm not gonna lie, I have no idea what timer does
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
        if globs.read_time:
            self.super_timer = timer()
            self.line.setText("%4.4f" % (self.super_timer - self.window_start_time))

    def closeEvent(self, a0):
        self.close()


# initialize the main window - class which contains all the initialization, GUI components, et cetera
# noinspection PyUnresolvedReferences
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
        self.tab4 = self.panTiltBox()
        self.tab5 = self.plunge_config()
        self.tabs.addTab(self.tab1, 'Plunge')
        self.tabs.addTab(self.tab2, 'A Axis')
        self.tabs.addTab(self.tab3, "Control Panel")
        self.tabs.addTab(self.tab4, "Pan/Tilt")
        self.tabs.addTab(self.tab5, "Plunge Config")
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
    # noinspection PyUnresolvedReferences
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
        self.homeButton.pressed.connect(motor.home)  # connect the button the operation function

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
        self.plungeButton.pressed.connect(motor.plunge)  # tie button to plunging operation


        self.timer_button = QPushButton()
        self.timer_button.setText("Show timer")
        self.timer_button.pressed.connect(self.open_timer_box)

        self.save_button = QPushButton()
        self.save_button.setText("Save last plunge")
        self.save_button.setFont(QFont('Munhwa Gothic', 25))
        self.save_button.setFixedSize(300, 80)
        self.save_button.setStyleSheet('''
                            QPushButton {
                                color: white; background-color : #CC7722;
                                border : 0px solid black;
                            }
                            QPushButton:pressed {
                                color: white; background-color : #99520c; border-radius : 15px;
                                border : 0px solid black;                              
                            }
                            ''')
        self.save_button.pressed.connect(stm.savePlungeData)

        self.save_name = QLineEdit()
        self.save_name.setText("Enter file name")
        self.save_name.setFont(QFont('Munhwa Gothic', 16))
        self.save_name.setFixedSize(300, 80)


        # create a vertical box layout - stacks QWidgets vertically
        vbox = QVBoxLayout()
        # add widgets to vbox
        vbox.addWidget(self.homeButton)
        vbox.addWidget(self.plungeButton)
        vbox.addWidget(self.timer_button)
        vbox.addWidget(self.save_button)
        vbox.addWidget(self.save_name)

        # set vbox to align at the center and top
        vbox.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        # set spacing between widgets
        vbox.setSpacing(40)
        groupBox.setLayout(vbox)
        return groupBox

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
        self.upNudge.pressed.connect(motor.upNudgeFunc)
        self.stopButton.clicked.connect(self.stopNudge)
        self.downNudge.pressed.connect(motor.downNudgeFunc)

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

    # function: stopNudge
    # purpose: stops nudge function
    # parameters: self
    # return: none
    def stopNudge(self):
        # reset settings to enable plunging and disable nudging
        self.startNudge.setEnabled(True)
        self.homeButton.setEnabled(True)
        self.plungeButton.setEnabled(True)
        self.upNudge.setEnabled(False)
        self.stopButton.setEnabled(False)
        self.downNudge.setEnabled(False)

        # reinitialize device and set it to disabled
        motor.clear_errors()

    # endregion nudgeBox_and_func

    # region panTilt
    def panTiltBox(self):
        groupBox = QGroupBox("Pan/Tilt Control")  # create a GroupBox

        self.tiltDown = QPushButton(self)
        self.tiltDown.setFixedSize(200, 200)
        self.tiltDown.setFont(QFont('Calibri', 30))
        self.tiltDown.setText("↓")
        self.tiltDown.setStyleSheet('QPushButton{color: white}')
        self.tiltDown.setStyleSheet('''
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

        self.tiltUp = QPushButton(self)
        self.tiltUp.setFixedSize(200, 200)
        self.tiltUp.setFont(QFont('Calibri', 30))
        self.tiltUp.setText("↑")
        self.tiltUp.setStyleSheet('QPushButton{color: white}')
        self.tiltUp.setStyleSheet('''
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
        self.panLeft = QPushButton(self)
        self.panLeft.setFixedSize(200, 200)
        self.panLeft.setFont(QFont('Calibri', 30))
        self.panLeft.setText("←")
        self.panLeft.setStyleSheet('QPushButton{color: white}')
        self.panLeft.setStyleSheet('''
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

        self.panRight = QPushButton(self)
        self.panRight.setFixedSize(200, 200)
        self.panRight.setFont(QFont('Calibri', 30))
        self.panRight.setText("→")
        self.panRight.setStyleSheet('QPushButton{color: white}')
        self.panRight.setStyleSheet('''
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

        self.pan_spinbox = QDoubleSpinBox(self)
        self.pan_spinbox.setMaximum(10)  # max nudge value
        self.pan_spinbox.setMinimum(0.1)  # min nudge value
        self.pan_spinbox.setValue(2)  # default value
        self.pan_spinbox.setSingleStep(0.1)  # incremental/decremental value when arrows are pressed
        self.pan_spinbox.setFont(QFont('Munhwa Gothic', 40))
        self.pan_spinbox.setStyleSheet('''
                                    QSpinBox::down-button{width: 400px}
                                    QSpinBox::up-button{width: 400px}
                                    ''')

        self.tilt_spinbox = QDoubleSpinBox(self)
        self.tilt_spinbox.setMaximum(10)  # max nudge value
        self.tilt_spinbox.setMinimum(0.1)  # min nudge value
        self.tilt_spinbox.setValue(2)  # default value
        self.tilt_spinbox.setSingleStep(0.05)  # incremental/decremental value when arrows are pressed
        self.tilt_spinbox.setFont(QFont('Munhwa Gothic', 40))
        self.tilt_spinbox.setStyleSheet('''
                                    QSpinBox::down-button{width: 400px}
                                    QSpinBox::up-button{width: 400px}
                                    ''')

        vbox = QGridLayout()

        self.tiltUp.pressed.connect(stm.tiltUpFunc)
        self.tiltDown.pressed.connect(stm.tiltDownFunc)
        self.panLeft.pressed.connect(stm.panLeftFunc)
        self.panRight.pressed.connect(stm.panRightFunc)

        vbox.addWidget(self.tiltUp, 0, 1)
        vbox.addWidget(self.tiltDown, 2, 1)
        vbox.addWidget(self.panLeft, 1, 0)
        vbox.addWidget(self.panRight, 1, 2)

        vbox.addWidget(self.tilt_spinbox, 3, 0, 1, 3)
        vbox.addWidget(self.pan_spinbox, 4, 0, 1, 3)

        # set alignment, spacing, and assign layout to groupBox
        vbox.setAlignment(Qt.AlignmentFlag.AlignTop)
        vbox.setSpacing(10)

        groupBox.setLayout(vbox)
        return groupBox

    # endregion panTilt

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
        self.A_spinbox_2.setMaximum(globs.A_TRAVEL_LENGTH_STEPS)  # max nudge value
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
        self.A_spinbox.setMaximum(globs.A_TRAVEL_LENGTH_STEPS)  # max nudge value
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
        self.A_start.clicked.connect(A_axis.A_start_func)
        self.A_up.clicked.connect(A_axis.A_up_func)
        self.A_stop.clicked.connect(A_axis.A_stop_func)
        self.A_down.clicked.connect(A_axis.A_down_func)
        self.A_home.clicked.connect(ni.A_home_func)
        self.A_move_to.clicked.connect(A_axis.A_move_to_func)

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

    # endregion nudgeBox_and_func

    # region control_panel
    # noinspection PyUnresolvedReferences
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
        self.brakeButton.stateChanged.connect(lambda: stm.brake_set(self.brakeButton.isChecked()))

        self.tempButton = QCheckBox(self)
        self.tempButton.setText("TEMP TOGGLE")
        self.tempButton.setFont(QFont('Munhwa Gothic', 30))
        self.tempButton.setStyleSheet("QCheckBox::indicator"
                                   "{"
                                   "width : 70px;"
                                   "height : 70px;"
                                   "}")
        self.tempButton.stateChanged.connect(self.tempToggle)

        self.resetButton = QPushButton(self)
        self.resetButton.setText("Reset stm")
        self.resetButton.pressed.connect(stm.reset)

        self.brakeBox = QSpinBox(self)
        self.brakeBox.setMaximum(16000)  # max nudge value
        self.brakeBox.setMinimum(1)  # min nudge value
        self.brakeBox.setValue(15000)  # default value
        self.brakeBox.setSingleStep(1)  # incremental/decremental value when arrows are pressed

        self.brakeBox.setFont(QFont('Munhwa Gothic', 40))
        self.brakeBox.setStyleSheet('''
                                    QSpinBox::down-button{width: 400px}
                                    QSpinBox::up-button{width: 400px}
                                    ''')

        vbox = QGridLayout()

        # column 1
        vbox.addWidget(self.brakeButton, 0, 0)
        vbox.addWidget(self.tempButton, 1, 0)
        vbox.addWidget(self.resetButton, 2, 0)

        # column 2
        vbox.addWidget(self.brakeBox, 1, 1)

        # set alignment, spacing, and assign layout to groupBox
        vbox.setAlignment(Qt.AlignmentFlag.AlignTop)
        vbox.setSpacing(10)

        groupBox.setLayout(vbox)
        return groupBox

    def plunge_config(self):
        groupBox = QGroupBox("Configuration")  # create GroupBox to hold QWidgets

        self.timepoint_label = QLabel(self)
        self.timepoint_label.setText("TIMEPOINT(ms)")
        self.timepoint_label.setFont(QFont('Munhwa Gothic', 30))

        self.timepoint_set_button = QPushButton(self)
        self.timepoint_set_button.setFixedSize(600, 50)

        self.timepoint_set_button.setFont(QFont('Munhwa Gothic', 16))
        self.timepoint_set_button.setText("Set timepoint")
        self.timepoint_set_button.clicked.connect(self.set_tp_func)

        self.timepoint_spinbox = QSpinBox(self)
        self.timepoint_spinbox.setMaximum(40000)  # max nudge value
        self.timepoint_spinbox.setMinimum(1)  # min nudge value
        self.timepoint_spinbox.setValue(1)  # default value
        self.timepoint_spinbox.setSingleStep(1)  # incremental/decremental value when arrows are pressed
        self.timepoint_spinbox.setFont(QFont('Munhwa Gothic', 30))
        self.timepoint_spinbox.setStyleSheet('''
                            QSpinBox::down-button{width: 20px; height: 15px}
                            QSpinBox::up-button{width: 20px; height: 15px}
                            ''')

        self.lift_after_plunge_button = QCheckBox(self)  # create a checkbox for turning on heater controller
        self.lift_after_plunge_button.setIconSize(QSize(100, 100))
        self.lift_after_plunge_button.setText("Lift a after plunge")
        self.lift_after_plunge_button.setFont(QFont('Munhwa Gothic', 30))
        self.lift_after_plunge_button.setStyleSheet('''
                                                QCheckBox::indicator {
                                                    width: 50px;
                                                    height: 50px;
                                                }''')

        self.lift_after_plunge_spinbox = QSpinBox(self)
        self.lift_after_plunge_spinbox.setMaximum(40000)  # max nudge value
        self.lift_after_plunge_spinbox.setMinimum(1)  # min nudge value
        self.lift_after_plunge_spinbox.setValue(2)  # default value
        self.lift_after_plunge_spinbox.setSingleStep(1)  # incremental/decremental value when arrows are pressed
        self.lift_after_plunge_spinbox.setFont(QFont('Munhwa Gothic', 30))
        self.lift_after_plunge_spinbox.setStyleSheet('''
                            QSpinBox::down-button{width: 20px; height: 15px}
                            QSpinBox::up-button{width: 20px; height: 15px}
                            ''')

        self.LN2_level_label = QLabel(self)
        self.LN2_level_label.setText("LN2 LEVEL SET")
        self.LN2_level_label.setFont(QFont('Munhwa Gothic', 30))

        self.b_on = QPushButton(self)
        self.b_on.setFixedSize(300, 50)
        self.b_on.setFont(QFont('Munhwa Gothic', 16))
        self.b_on.setText("Brake on")
        self.b_on.clicked.connect(lambda: stm.brake_set(True))

        self.b_off = QPushButton(self)
        self.b_off.setFixedSize(300, 50)
        self.b_off.setFont(QFont('Munhwa Gothic', 16))
        self.b_off.setText("Brake off")
        self.b_off.clicked.connect(lambda: stm.brake_set(False))

        self.LN2_level_set = QPushButton(self)
        self.LN2_level_set.setFixedSize(610, 50)
        self.LN2_level_set.setFont(QFont('Munhwa Gothic', 16))
        self.LN2_level_set.setText("Set LN2 level")
        self.LN2_level_set.clicked.connect(self.ln2_level_set_func)

        self.LN2_level_spinbox = QSpinBox(self)
        self.LN2_level_spinbox.setFixedSize(400, 110)
        self.LN2_level_spinbox.setMaximum(40000)  # max nudge value
        self.LN2_level_spinbox.setMinimum(1)  # min nudge value
        self.LN2_level_spinbox.setValue(2)  # default value
        self.LN2_level_spinbox.setSingleStep(1)  # incremental/decremental value when arrows are pressed
        self.LN2_level_spinbox.setFont(QFont('Munhwa Gothic', 30))
        self.LN2_level_spinbox.setStyleSheet('''
                            QSpinBox::down-button{width: 20px; height: 15px}
                            QSpinBox::up-button{width: 20px; height: 15px}
                            ''')
        self.a_offset_label = QLabel(self)
        self.a_offset_label.setText("LOOP OFFSET")
        self.a_offset_label.setFont(QFont('Munhwa Gothic', 30))

        self.home_p = QPushButton(self)
        self.home_p.setFixedSize(300, 50)
        self.home_p.setFont(QFont('Munhwa Gothic', 16))
        self.home_p.setText("Plunge home")
        self.home_p.clicked.connect(motor.home)

        self.home_a = QPushButton(self)
        self.home_a.setFixedSize(300, 50)
        self.home_a.setFont(QFont('Munhwa Gothic', 16))
        self.home_a.setText("A home")
        self.home_a.clicked.connect(ni.A_home_func)

        self.up_a = QPushButton(self)
        self.up_a.setFixedSize(300, 50)
        self.up_a.setFont(QFont('Munhwa Gothic', 16))
        self.up_a.setText("A up")
        self.up_a.clicked.connect(A_axis.A_up_func)

        self.down_a = QPushButton(self)
        self.down_a.setFixedSize(300, 50)
        self.down_a.setFont(QFont('Munhwa Gothic', 16))
        self.down_a.setText("A down")
        self.down_a.clicked.connect(A_axis.A_down_func)

        self.set_a_offset = QPushButton(self)
        self.set_a_offset.setFixedSize(610, 50)
        self.set_a_offset.setFont(QFont('Munhwa Gothic', 16))
        self.set_a_offset.setText("Set A offset")
        self.set_a_offset.clicked.connect(self.set_a_offset_func)

        self.a_offset_spinbox = QSpinBox(self)
        self.a_offset_spinbox.setFixedSize(400, 170)
        self.a_offset_spinbox.setMaximum(40000)  # max nudge value
        self.a_offset_spinbox.setMinimum(0)  # min nudge value
        self.a_offset_spinbox.setValue(2)  # default value
        self.a_offset_spinbox.setSingleStep(1)  # incremental/decremental value when arrows are pressed
        self.a_offset_spinbox.setFont(QFont('Munhwa Gothic', 30))
        self.a_offset_spinbox.setStyleSheet('''
                            QSpinBox::down-button{width: 20px; height: 15px}
                            QSpinBox::up-button{width: 20px; height: 15px}
                            ''')



        # create vertical box layout
        gridbox= QGridLayout()
        # add widgets to the box
        gridbox.addWidget(self.timepoint_label, 0, 0, 1, 1)
        gridbox.addWidget(self.timepoint_set_button, 0, 1, 1, 2)
        gridbox.addWidget(self.timepoint_spinbox, 0, 3, 1, 1)

        gridbox.addWidget(self.lift_after_plunge_button, 1, 1, 1, 2)
        gridbox.addWidget(self.lift_after_plunge_spinbox, 1, 3, 1, 1)

        gridbox.addWidget(self.LN2_level_label, 2, 0, 2, 1)
        gridbox.addWidget(self.b_on, 2, 1, 1, 1)
        gridbox.addWidget(self.b_off, 2, 2, 1, 1)
        gridbox.addWidget(self.LN2_level_set, 3, 1, 1, 2)
        gridbox.addWidget(self.LN2_level_spinbox, 2, 3, 2, 1)

        gridbox.addWidget(self.a_offset_label, 4, 0, 3, 1)
        gridbox.addWidget(self.home_p, 4, 1, 1, 1)
        gridbox.addWidget(self.home_a, 4, 2, 1, 1)
        gridbox.addWidget(self.up_a, 5, 1, 1, 1)
        gridbox.addWidget(self.down_a, 5, 2, 1, 1)
        gridbox.addWidget(self.set_a_offset, 6, 1, 1, 2)
        gridbox.addWidget(self.a_offset_spinbox, 4, 3, 3, 1)
        # set spacing between widgets
        gridbox.setSpacing(10)
        gridbox.setAlignment(Qt.AlignmentFlag.AlignTop)
        groupBox.setLayout(gridbox)  # set layout for groupBox
        return groupBox

    # TODO: move this to somewhere else. GUI.py is ideally only for GUI setup and trivial logic at most
    def ln2_level_set_func(self):
        globs.ln2_level = -1*int(motor.get_position())
        print("ln2 level: " + str(globs.ln2_level))
        self.LN2_level_spinbox.setValue(int(globs.ln2_level*globs.P_UM_PER_TICK))

    def set_a_offset_func(self):
        globs.a_offset = globs.a_position
        print("a_offset: " + str(globs.a_offset))

    def set_tp_func(self):
        globs.timepoint = int(self.timepoint_spinbox.value())  # in ms
        i = 0
        for position in globs.plungePosData:
            if position > globs.ln2_level:
                break
            i += 1
        # interpolate time of ln2 contact
        ln2_time = globs.plungeTime[i-1] + (globs.plungeTime[i] - globs.plungeTime[i-1])/\
                   (globs.plungePosData[i] - globs.plungePosData[i-1])*\
                   (globs.plungePosData[i]-globs.ln2_level)

        print("ln2_time" + str(ln2_time))

        dep_time = ln2_time - globs.timepoint # time that the deposition should occur
        i = 0
        for t in globs.plungeTime:
            i += 1
            if t > dep_time:
                break

        # interpolate deposition position. Unit is plunge encoder pulses
        dep_pos = globs.plungePosData[i - 1] + (globs.plungePosData[i] - globs.plungePosData[i - 1]) / \
            (globs.plungeTime[i] - globs.plungeTime[i - 1]) * \
            (globs.plungeTime[i] - dep_time)
        print("dep_pos" + str(dep_pos))

        globs.dep_pos_um = dep_pos * globs.P_UM_PER_TICK # convert to um
        dep_pos_a_steps = globs.dep_pos_um * globs.A_STEPS_PER_UM

        # TODO: determine if speed change is necessary to achieve desired tp


        ni.A_home_func()
        print("moving a steps" + str(abs(int(dep_pos_a_steps + globs.a_offset))))
        A_axis.A_move(globs.A_DOWN, abs(int(dep_pos_a_steps + globs.a_offset)))

    def tempToggle(self):
        globs.readTemp_flag = self.tempButton.isChecked()

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
        self.vac.stateChanged.connect(lambda: ni.ni_set('vacuum',  (not self.vac.isChecked())))

        # set enable state of checkboxes
        self.h_controller_check.setEnabled(True)
        self.h_power.setEnabled(True)
        self.vac.setEnabled(True)
        #Initially have all checkboxes to be true since it was initialized in main function
        self.h_controller_check.setChecked(True)
        self.h_power.setChecked(True)
        self.vac.setChecked(True)
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
        self.instant_temp_button.pressed.connect(ni.getT)
        self.temp_h_box.addWidget(self.instant_temp_button)

        self.instant_temp_label = QLabel("")
        self.instant_temp_label.setText("Read Temperature")
        self.instant_temp_label.setFont(QFont('Munhwa Gothic', 20))
        self.temp_h_box.addWidget(self.instant_temp_label)

        self.profile_temp_button = QPushButton(self)
        self.profile_temp_button.setText("🤒📈")
        self.profile_temp_button.pressed.connect(ni.collect_temp_profile)
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

    # function: guiheater_controller
    # purpose: turns on or off heater controller depending on checkbox status
    # parameters: self
    # return: none
    def guiheater_controller(self):
        if self.h_controller_check.isChecked() == False:
            self.h_power.setChecked(False)
        ni.ni_set('heater_controller', self.h_controller_check.isChecked())

    # function: guiheater_power
    # purpose: turn heater on or off depending on checkbox status; will not turn on without controller being on
    # parameters: self
    # return: none
    def guiheater_power(self):
        if self.h_power.isChecked():
            self.h_controller_check.setChecked(True)
        ni.ni_set('heater', self.h_power.isChecked())


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
        self.plungevac.setEnabled(True)

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
        self.graphVel.setTitle("Plunge Cooler Position vs Time", color="w", size="10pt")
        styles = {"color": "white", "font-size": "10px"}
        self.graphVel.setLabel("left", "Position (cm)", **styles)
        self.graphVel.setLabel("bottom", "Time (ms)", **styles)
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

        act1.triggered.connect(closeGUI())
        context.exec(e.globalPos())


def closeGUI():
    print("Force exiting application")
    ni.ni_set('vacuum',            True)
    ni.ni_set('heater',            True)
    ni.ni_set('heater_controller', False)
    ni.ni_set('light',             False)

    motor.close()
    QApplication.closeAllWindows()
    sys.exit(0)

