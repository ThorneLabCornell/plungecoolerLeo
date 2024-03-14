import globals as globs
import time
from timeit import default_timer as timer
import ni
import threading


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

