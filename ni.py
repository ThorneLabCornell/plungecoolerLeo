import nidaqmx
import time
import globals as globs
from timeit import default_timer as timer
import datetime
import threading
import motor


# NI DAQ configuration and pinout
DEVICE_NAME = "Dev3"
PINOUT = { # too lazy to implement and enum right now
    'plunge_home':          DEVICE_NAME + "/port1/line4",
    'vacuum':               DEVICE_NAME + "/port0/line2",
    'heater':               DEVICE_NAME + "/port0/line3",
    'heater_controller':    DEVICE_NAME + "/port0/line6",
    'light':                DEVICE_NAME + "/port0/line3",
    'temperature':          DEVICE_NAME + "/ai10",
    'A_step':               DEVICE_NAME + "/port2/line4",
    'A_dir':                DEVICE_NAME + "/port2/line1",
    'A_en':                 DEVICE_NAME + "/port2/line6",
    'A_home':               DEVICE_NAME + "/port2/line0",#A axis limit switch signal
    'A_motor_power':        DEVICE_NAME + "/port0/line5",
    'thermocouple':         DEVICE_NAME + "/ai6",
    'stm_rst':              DEVICE_NAME + "/port1/line2",
    'microdrop_trig':       DEVICE_NAME+ "/port1/line6"#port 5 on daq
}

#testing code gary
def reset_stm():
    with nidaqmx.Task() as task:
        task.do_channels.add_do_chan(PINOUT['stm_rst'])
        task.start()
        print("resetting stm")
        task.write(False)
        time.sleep(.5)
        task.write(True)

        task.stop()
    time.sleep(2)


# general function for toggling any digital out line on the ni daq
def ni_set(device, value):
    with nidaqmx.Task() as task:
        task.do_channels.add_do_chan(PINOUT[device]) #device is in pinout list above (digital outputs)
        task.start()
        print(device + " set to " + str(value)) #value is set to true or false
        task.write(value)
        #time.sleep(.5)
        task.stop()


def read_temperature():#used read temperature over plunge path
    # reads voltages into a global array
    start_time = timer()
    with nidaqmx.Task() as tempTask:
        sampling_rate = 2000000  # can alter sampling rate for quicker time points depending on DAQ max reads (unit in Hz)
        try:
            tempTask.ai_channels.add_ai_voltage_chan(PINOUT['temperature']) #analog input for temp
            # sets sample rate, clock source "" sets to internal clock of the device is used, data is acquired on rising edge of analog input
            tempTask.timing.cfg_samp_clk_timing(sampling_rate, source="", active_edge=nidaqmx.constants.Edge.RISING)

            val = tempTask.read() #read temperature
            globs.plungeTemp.append(val) #records temperature in global array (plungeTemp)
            globs.plunge_temp_time.append(timer() - start_time) #record current time point
        finally:
            return


def startHome():
    home_task = nidaqmx.Task()
    home_task.di_channels.add_di_chan(PINOUT['plunge_home']) #set digital input to plunge home pin locatoin
    home_task.start()
    return home_task #return plunge home pin channel


# captures the next 5 seconds of temp data using thermocouple
def tempLog(sample_seconds=5, sampling_rate=20000, log=True): #why is sampling rate lower than read_temperature
    with nidaqmx.Task() as tempTask:
        num_samples = sampling_rate * sample_seconds #Hz*time
        tempTask.ai_channels.add_ai_voltage_chan(PINOUT['thermocouple'])
        # sets sample rate, clock source "" sets to internal clock
        tempTask.timing.cfg_samp_clk_timing(sampling_rate, source="", active_edge=nidaqmx.constants.Edge.RISING,
                                            sample_mode=nidaqmx.constants.AcquisitionType.FINITE, #used to specify task acquire finite samples
                                            samps_per_chan=num_samples)#used to specify number of sample to acquire

        print("done collecting T")
        temps = tempTask.read(number_of_samples_per_channel=num_samples) #read set amount of sample data
        if log:
            filename = "C:\\Users\\ret-admin\\Desktop\\plunge_data\\temp\\"
            filename += datetime.datetime.now().strftime("%m-%d-%Y.%H-%M-%S")
            f = open(filename + '.txt', 'w')
            for temp in temps:
                f.write(str(temp) + '\n')
            f.close()
        else:
            global current_probe_temp
            current_probe_temp = (sum(temps) / len(temps)) #average temperature over 5 seconds
        print("regained temperature thread")
        tempTask.stop()


def getT(self): #no idea what this is used for
    logT = threading.Thread(target=tempLog, args=(1, 100, False)) #run templog function from above (running in parallel with gui)
    logT.start()
    logT.join() #waits for templog function to be completed before moving on
    self.instant_temp_label.setText("%4.2f°C" % (globs.current_probe_temp)) #update UI with current average temperature (confirm with john)


def collect_temp_profile(self):
    self.graphTempPos.clear()
    globs.plungeTemp.clear()
    globs.plunge_temp_time.clear()
    #gui code
    self.graphTempPos.setTitle("Plunge Cooler Temperature vs Position", color="w", size="10pt")
    styles = {"color": "white", "font-size": "10px"}
    self.graphTempPos.setLabel("left", "Voltage (V)", **styles)
    self.graphTempPos.setLabel("bottom", "Position (cm)", **styles)
    print("Nudging down specified amount in 'nudge' to collect profile....")

    # create storage variables (Py arrays) for data
    testSet = []
    testPos = []
    value_n = (-1 * (motor.get_position() * globs.leadscrew_inc / globs.encoder_pulse_num)) + self.nudge_spinbox.value()  # approximate updated position
    x = 0
    while (x < 200):
        read_temperature()
        testSet.append(val)
        testPos.append(timer())
        x = x + 1
        value_n = (-1 * ( motor.get_position() * globs.leadscrew_inc / globs.encoder_pulse_num)) + self.nudge_spinbox.value()  # approximate updated position
    print(testSet)
    motor.move_nudge("down", self.nudge_spinbox.value())  # calculate nudge value from input & move
    value_n = (-1 * (
            motor.get_position() * globs.leadscrew_inc / globs.encoder_pulse_num)) + self.nudge_spinbox.value()  # approximate updated position
    # time.sleep(0.1)
    self.current_pos_label.setText("%4.2f cm" % (value_n))  # update position label
    self.graphTempPos.plot(testPos, testSet)


def A_home_func(self):
    ni_set('A_motor_power', True)
    ni_set('A_dir', globs.A_UP)  # TODO: Switch to A_UP when i move lim sw
    step_task = nidaqmx.Task()
    step_task.do_channels.add_do_chan(PINOUT['A_step'])
    step_task.start()
    home_task = nidaqmx.Task()
    home_task.di_channels.add_di_chan(PINOUT['A_home'])
    home_task.start()
    while True:
        step_task.write(True)
        time.sleep(globs.A_SPEED) #what does A_SPEED have to do with sleep time
        step_task.write(False) 
        time.sleep(globs.A_SPEED)
        if home_task.read():#limit switch triggers
            break
    globs.a_position = 0 #set position to home
    globs.gui.A_pos_label.setText(str(0))#update gui on A axis position

    home_task.stop()
    step_task.stop()

def A_move_thread(direc, steps):
    ni_set('A_motor_power', True) #give power to stepper motor
    ni_set('A_dir', direc) #direc (True/False) define turn direction
    with nidaqmx.Task() as step_task:
        step_task.do_channels.add_do_chan(PINOUT['A_step']) #move motor by amount of steps desired
        step_task.start()
        for i in range(steps):
            step_task.write(True)
            time.sleep(globs.A_SPEED)
            step_task.write(False)
            time.sleep(globs.A_SPEED)
        step_task.stop()

def drop_dispense():
    ni_set('microdrop_trig', False) #give power to stepper
    ni_set('microdrop_trig', True)
    ni_set('microdrop_trig', False)  # give power to stepper

