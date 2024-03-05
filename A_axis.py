import globals as globs
import time
from timeit import default_timer as timer
import ni
import threading


# function: nudgeBegin
# purpose: initializes the device to receive nudge inputs via the buttons & disables plunge functionality
# parameters: self
# return: none
def A_start_func(self):
    ni.ni_set('A_en', False) #set enable signal to low to allow motor movement
    # ni_set('light', True)  # turn on light to indicate movement stage
    # disable plunge, home, startNudge buttons, enable control buttons and stop nudge buttons in GUI (figured out by Gary after 3hrs:))
    globs.gui.A_home.setEnabled(True)
    globs.gui.A_up.setEnabled(True)
    globs.gui.A_stop.setEnabled(True)
    globs.gui.A_down.setEnabled(True)
    globs.gui.A_move_to.setEnabled(True)
    print("start")


# function: A_up_func
# purpose: nudges the carriage up
# parameters: self
# return: none
def A_up_func(self):
    new_pos = globs.a_position - int(globs.gui.A_spinbox.value()) #A_spinbox.value() is what user inputs in GUI
    A_move(globs.A_UP, int(globs.gui.A_spinbox.value()))#A_UP is TRUE
    globs.gui.current_pos_label.setText(str(new_pos))  # update position label in GUI


# function: A_stop_func
# purpose: stops nudge function
# parameters: self
# return: none
def A_stop_func(self):
    ni.ni_set('A_en', True)#set enable signal to high to stop motor movement
    #disable control buttons and stop nudge buttons in GUI
    globs.gui.A_up.setEnabled(False)
    globs.gui.A_stop.setEnabled(False)
    globs.gui.A_down.setEnabled(False)
    globs.gui.A_home.setEnabled(False)
    globs.gui.A_move_to.setEnabled(False)


# function: downNudgeFunc
# purpose: nudges the carriage down
# parameters: self
# return: none
def A_down_func(self):
    new_pos = globs.a_position + int(globs.gui.A_spinbox.value())
    A_move(globs.A_DOWN, int(globs.gui.A_spinbox.value()))
    globs.gui.A_pos_label.setText(str(new_pos))  # update position label


def A_move_to_func(self):
    to_pos = int(globs.gui.A_spinbox_2.value())
    direction = globs.A_UP if to_pos > globs.a_position else globs.A_DOWN
    amount = abs(globs.a_position - to_pos)
    A_move(direction, amount)


def A_move(direc, steps):
    #direction algorithm
    if direc == globs.A_UP:
        globs.a_position -= steps
    else:
        globs.a_position += steps
    moveT = threading.Thread(target=ni.A_move_thread, args=(direc, steps))
    moveT.start()#invokes A.movethread to be ran in parallel to current program (taking in inputs of direc and steps)

