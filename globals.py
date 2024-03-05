'''globals file for passing data between gui and main program'''
gui = None

plungeData = []
plungeTime = []
plungeTemp = []
plungePosData = []
plungeVelData = []
plunge_temp_time = []
timepoint = 0
a_offset = 0
a_position = 5000

ln2_level = 25000
plunge_speed = -8000

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
current_probe_temp = 0

'''constants for A stepper motor'''
A_UP = True
A_DOWN = False
A_SPEED = .001
A_TRAVEL_LENGTH_STEPS = 10000  # arbitrary right now
A_STEPS_PER_UM = 200/8/1000    # 200 steps/rotation, 8mm per turn, 1000um per mm



pos_home_raw = 38000 # TODO: fully deprecate this