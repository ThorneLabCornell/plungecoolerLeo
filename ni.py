import nidaqmx
import time
import globals as globs
from timeit import default_timer as timer
import datetime
import threading
import motor


# NI DAQ configuration and pinout
DEVICE_NAME = "Dev1"
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
    'A_home':               DEVICE_NAME + "/port2/line0",
    'A_motor_power':        DEVICE_NAME + "/port0/line5",
    'thermocouple':         DEVICE_NAME + "/ai6",
    'stm_rst':              DEVICE_NAME + "/port1/line2"
}


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
def ni_set(device: object, value: object) -> object:
    with nidaqmx.Task() as task: #variable callout
        task.do_channels.add_do_chan(PINOUT[device])
        task.start()
        print(device + " set to " + str(value))
        task.write(value)
        #time.sleep(.5)
        task.stop()


def read_temperature():
    # reads voltages into a global array
    start_time = timer()
    with nidaqmx.Task() as tempTask:
        sampling_rate = 2000000  # can alter sampling rate for quicker time points depending on DAQ max reads
        try:
            tempTask.ai_channels.add_ai_voltage_chan(PINOUT['temperature'])
            # sets sample rate, clock source "" sets to internal clock
            tempTask.timing.cfg_samp_clk_timing(sampling_rate, source="", active_edge=nidaqmx.constants.Edge.RISING)

            val = tempTask.read()
            globs.plungeTemp.append(val)
            globs.plunge_temp_time.append(timer() - start_time)
        finally:
            return


def startHome():
    home_task = nidaqmx.Task()
    home_task.di_channels.add_di_chan(PINOUT['plunge_home'])
    home_task.start()
    return home_task


# captures the next 5 seconds of temp data
def tempLog(sample_seconds=5, sampling_rate=20000, log=True):
    with nidaqmx.Task() as tempTask:
        num_samples = sampling_rate * sample_seconds
        tempTask.ai_channels.add_ai_voltage_chan(PINOUT['thermocouple'])
        # sets sample rate, clock source "" sets to internal clock
        tempTask.timing.cfg_samp_clk_timing(sampling_rate, source="", active_edge=nidaqmx.constants.Edge.RISING,
                                            sample_mode=nidaqmx.constants.AcquisitionType.FINITE,
                                            samps_per_chan=num_samples)

        print("done collecting T")
        temps = tempTask.read(number_of_samples_per_channel=num_samples)
        if log:
            filename = "C:\\Users\\ret-admin\\Desktop\\plunge_data\\temp\\"
            filename += datetime.datetime.now().strftime("%m-%d-%Y.%H-%M-%S")
            f = open(filename + '.txt', 'w')
            for temp in temps:
                f.write(str(temp) + '\n')
            f.close()
        else:
            global current_probe_temp
            current_probe_temp = (sum(temps) / len(temps))
        print("regained temperature thread")
        tempTask.stop()


def getT(self):
    logT = threading.Thread(target=tempLog, args=(1, 100, False))
    logT.start()
    logT.join()
    self.instant_temp_label.setText("%4.2f°C" % (globs.current_probe_temp))


def collect_temp_profile(self):
    self.graphTempPos.clear()
    globs.plungeTemp.clear()
    globs.plunge_temp_time.clear()

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

# TODO: Move into a_axis.py
def A_home_func():
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
        time.sleep(globs.A_SPEED)
        step_task.write(False)
        time.sleep(globs.A_SPEED)
        if home_task.read():
            break
    globs.a_position = 0
    globs.gui.A_pos_label.setText(str(0))

    home_task.stop()
    step_task.stop()

def A_move_thread(direc, steps):
    ni_set('A_motor_power', True)
    ni_set('A_dir', direc)
    with nidaqmx.Task() as step_task:
        step_task.do_channels.add_do_chan(PINOUT['A_step'])
        step_task.start()
        for i in range(steps):
            step_task.write(True)
            time.sleep(globs.A_SPEED)
            step_task.write(False)
            time.sleep(globs.A_SPEED)
        step_task.stop()
