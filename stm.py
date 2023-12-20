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
ser = serial.Serial('COM6', 115200, timeout=1.5)



def clear_input():
    global ser
    ser.reset_input_buffer()


def brake_set(state):
    print("brakin")
    if state:
        ser.write(bytes(BRAKE + '\r\n', 'utf-8'))  # brake
    else:
        ser.write(bytes(RELEASE + '\r\n', 'utf-8'))  # release
    ser.readline()
#    print(resp)
#    ser.reset_input_buffer() # clear any input
    print("broke")


def wait_for_ack():
    ser.readline()


def write(msg):
    ser.write(msg)


# TODO: pop up gui to ask if save data since we dont want to save for every plunge
# optionally, instead just have a button in the main plunge window that loads globs.plungePoseData into a file
def receivePlungeData():
    i = 0
    f = open("xd.txt", 'w')
    while True:
        log = ser.readline().decode('utf-8').strip()

        if log == ACK:  # ack at end of transmission
            break
        else:
            i += 1
            globs.plungePosData.append(int(log)*2)  # *2 because the stm, counts half as many encoder ppr
            globs.plungeTime.append(i*.02)
            # also update velocity
            f.write(str(log))
            f.write('\t')
            f.write(str(i*.02))
            f.write('\n')
    print(globs.plungePosData)
    f.close()


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


def reset():
    global ser
    ser.close()
    ni.reset_stm()
    ser = serial.Serial('COM6', 115200)  # open serial port
