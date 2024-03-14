""" globals file for passing data between gui and main program """

gui = None  # stores gui once created, so it can be referenced from anywhere

plungeData = []     # unused. TODO: deprecate.
plungeTime = []     # times that the above data is taken at in us
plungeTemp = []     # if collecting temp, store here
plunge_temp_time = []   # times of temp data
plungePosData = []  # positions logged from plunge, stored in encoder pulses, as understood by the epos
                    # a note: the stm counts half as many encoder pulses as the epos does. something to do with
                    # I believe this is due to counting both edges vs only rising edges. not the end of the world
plungeVelData = []  # velocity. currently unimplemented

timepoint = 0       # target timepoint for plunge in ms
a_offset = 0        # A axis posn where the loop is level with the homed plunger tip
a_position = 5000   # current posn of A axis
Dispenser_position = 5000   # current posn of Dispenser axis

ln2_level = 25000       # in plunge encoder steps
plunge_speed = -8000    # negative for downwards motion. 8000=1.6ish m/s,10000 = 2ish m/s

'''assorted flags'''
plunge_done_flag = False
readTemp_flag = False
read_time = False
'''main plunge axis constants'''
leadscrew_inc = 1.2
encoder_pulse_num = 512 * 4
P_CM_PER_TICK = (leadscrew_inc / encoder_pulse_num)
P_UM_PER_TICK = P_CM_PER_TICK * 10 * 1000
P_TICKS_PER_UM = 1 / P_UM_PER_TICK
dep_pos_um = 0

current_probe_temp = 0

'''constants for A stepper motor'''
A_UP = True
A_DOWN = False
A_SPEED = .001
A_TRAVEL_LENGTH_STEPS = 10000  # arbitrary right now
A_STEPS_PER_UM = 200/8/1000    # 200 steps/rotation, 8mm per turn, 1000um per mm

# actual times recorded from plunge
true_dep_time = 0
true_timepoint = 0
true_ln2_time = 0

pos_home_raw = 38000 # TODO: fully deprecate this. it no longer aligns with reality but some code references it

#dispenser delay time (s)
# actual dispenser_delay=0.004079345035 per drop (1ms delay from each drop)
dispenser_delay=0.01 #delay by 10ms 