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
    ni.ni_set('A_en', False)
    # ni_set('light', True)  # turn on light to indicate movement stage
    # disable plunge, home, startNudge buttons, enable control buttons and stop nudge buttons
    globs.gui.A_home.setEnabled(True)
    globs.gui.A_up.setEnabled(True)
    globs.gui.A_stop.setEnabled(True)
    globs.gui.A_down.setEnabled(True)
    globs.gui.A_move_to.setEnabled(True)


# function: A_up_func
# purpose: nudges the carriage up
# parameters: self
# return: none
def A_up_func():
    new_pos = globs.a_position - int(globs.gui.A_spinbox.value())
    A_move(globs.A_UP, int(globs.gui.A_spinbox.value()))
    globs.gui.A_pos_label.setText(str(new_pos))  # update position label


# function: A_stop_func
# purpose: stops nudge function
# parameters: self
# return: none
def A_stop_func(self):
    ni.ni_set('A_en', True)

    globs.gui.A_up.setEnabled(False)
    globs.gui.A_stop.setEnabled(False)
    globs.gui.A_down.setEnabled(False)
    globs.gui.A_home.setEnabled(False)
    globs.gui.A_move_to.setEnabled(False)


# function: downNudgeFunc
# purpose: nudges the carriage down
# parameters: self
# return: none
def A_down_func():
    new_pos = globs.a_position + int(globs.gui.A_spinbox.value())
    A_move(globs.A_DOWN, int(globs.gui.A_spinbox.value()))
    globs.gui.A_pos_label.setText(str(new_pos))  # update position label


def A_move_to_func():
    to_pos = int(globs.gui.A_spinbox_2.value())
    direction = globs.A_UP if to_pos > globs.a_position else globs.A_DOWN
    amount = abs(globs.a_position - to_pos)
    A_move(direction, amount)


def A_move(direc, steps):
    # update a position tracker
    if direc == globs.A_UP:
        globs.a_position -= steps
    else:
        globs.a_position += steps
    # move in a thread so gui still works. actual pulses sent from function in ni.py
    moveT = threading.Thread(target=ni.A_move_thread, args=(direc, steps))
    moveT.start()

