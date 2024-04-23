import globals as globs
import serial
import ni

# serial constants
# TODO: move these into a json or similar to easily share between python and stm32 scripts
ACK     = 'Z'
BAD     = 'X'
PLUNGE  = '2'
MOVE    = '3'
BRAKE   = '5'
RELEASE = '4'

# open serial port. timeout should b e sufficient for any operation to finish.
# timeout prevents crash in case of communication failure11111111111
ser = serial.Serial('COM4', 115200, timeout=1.5)

# ignore all past/pending inputs on the serial port
def clear_input():
    global ser
    ser.reset_input_buffer()

# set brake state
def brake_set(state):
    print("brakin")
    if state:
        ser.write(bytes(BRAKE + '\r\n', 'utf-8'))  # brake
    else:
        ser.write(bytes(RELEASE + '\r\n', 'utf-8'))  # release
    print(ser.readline())
    print("broke")

# blocks until gui sends ack character
def wait_for_ack():
    print("waiting")
    print(ser.readline())
    print("done")

# sends msg to stm32
def write(msg):
    ser.write(msg)

# listens to data stm is sending and distributes it into the global arrays
# TODO: put this in a thread so gui can be used while transfer occurs.
def receivePlungeData():
    i = 0
    dep_flag = False
    ln2_flag = False
    print("LN2 LEVEL: " + str(globs.ln2_level))
    print("A   LEVEL: " + str(globs.dep_pos_um))

    while True:
        # TODO: moving average for velocity, same algo as in stm code
        log = ser.readline().decode('utf-8').strip()
        if log == ACK:  # ack at end of transmission
            break
        else:
            #print(log)
            #pos_ticks = int(log)*2 #debug
            if log:  # Check if log is not empty
                try:
                    pos_ticks = int(log) * 2
                    pos_um = pos_ticks * globs.P_UM_PER_TICK
                    globs.plungePosData.append(pos_ticks)  # *2 because the stm, counts half as many encoder ppr
                    globs.plungeTime.append(i * .02)
                    if pos_um > globs.dep_pos_um and not dep_flag:  # grab time it plunged thru loop
                        print("DEP TIME")
                        globs.true_dep_time = globs.plungeTime[i]
                        dep_flag = True
                    if pos_um > globs.ln2_level * globs.P_UM_PER_TICK and not ln2_flag:  # grab time it plunged into LN2 level
                        globs.true_ln2_time = globs.plungeTime[i]
                        globs.true_timepoint = globs.true_ln2_time - globs.true_dep_time
                        ln2_flag = True
                    i += 1
                except ValueError:
                    print("Error: log contains a non-numeric value")
            else:
                print("Error: log is empty")
            # pos_um = pos_ticks * globs.P_UM_PER_TICK
            # globs.plungePosData.append(pos_ticks)  # *2 because the stm, counts half as many encoder ppr
            # globs.plungeTime.append(i*.02)
            # if pos_um > globs.dep_pos_um and not dep_flag: # grab time it plunged thru loop
            #     print("DEP TIME")
            #     globs.true_dep_time = globs.plungeTime[i]
            #     dep_flag = True
            # if pos_um > globs.ln2_level*globs.P_UM_PER_TICK and not ln2_flag:   # grab time it plunged into LN2 level
            #     globs.true_ln2_time = globs.plungeTime[i]
            #     globs.true_timepoint = globs.true_ln2_time - globs.true_dep_time
            #     ln2_flag = True
            # i += 1

    print(globs.plungePosData)
    print("True TP: " + str(globs.true_timepoint))


''' Pan/tilt control callers '''
def tiltUpFunc(self):
    self.movePanTilt('1', self.tilt_spinbox.value())


def tiltDownFunc(self):
    self.movePanTilt('2', self.tilt_spinbox.value())


def panLeftFunc(self):
    self.movePanTilt('3', self.pan_spinbox.value())


def panRightFunc(self):
    self.movePanTilt('4', self.pan_spinbox.value())


def movePanTilt(self, axis, amt):
    msg = "1"
    msg += axis
    msg += str(int(amt*100)).zfill(4)  # amt*100 ensures integer
    print(msg)
    ser.write(bytes(msg, 'utf-8'))

# physically reset the stm32 and re-open communcations
def reset():
    global ser
    ser.close() # gracefully close serial port
    ni.reset_stm()  # physically reset
    ser = serial.Serial('COM6', 115200)  # reopen serial port


# saves plunge data into xd.txt
def savePlungeData():
    print("called save")
    f = open(str(globs.gui.save_name.displayText()) + ".txt", 'w')
    i = 0
    for log in globs.plungePosData:
        f.write(str(int(log*globs.P_UM_PER_TICK)))  # current position in um. int() for rounding
        f.write('\t')  # tab character
        f.write(str(int(globs.plungeTime[i])))  # time in us
        f.write('\n')  # newline
        i += 1
    f.write("timepoint: " + str(globs.true_timepoint))

    f.close()
