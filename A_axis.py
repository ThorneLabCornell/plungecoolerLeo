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
    self.A_home.setEnabled(True)
    self.A_up.setEnabled(True)
    self.A_stop.setEnabled(True)
    self.A_down.setEnabled(True)
    self.A_move_to.setEnabled(True)


# function: A_up_func
# purpose: nudges the carriage up
# parameters: self
# return: none
def A_up_func(self):
    new_pos = globs.a_position - int(self.A_spinbox.value())
    A_move(globs.A_UP, int(self.A_spinbox.value()))
    self.current_pos_label.setText(str(new_pos))  # update position label


# function: A_stop_func
# purpose: stops nudge function
# parameters: self
# return: none
def A_stop_func(self):
    ni.ni_set('A_en', True)

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
    new_pos = globs.a_position + int(self.A_spinbox.value())
    A_move(globs.A_DOWN, int(self.A_spinbox.value()))
    self.A_pos_label.setText(str(new_pos))  # update position label


def A_move_to_func(self):
    to_pos = int(self.A_spinbox_2.value())
    direction = globs.A_UP if to_pos > globs.a_position else globs.A_DOWN
    amount = abs(globs.a_position - to_pos)
    A_move(direction, amount)


def A_move(direc, steps):
    if direc == globs.A_UP:
        globs.a_position -= steps
    else:
        globs.a_position += steps
    moveT = threading.Thread(target=ni.A_move_thread, args=(direc, steps))
    moveT.start()

