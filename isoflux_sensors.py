#!/usr/bin/python
# -*- coding: utf-8 -*-
#  IsoFlux sensor definition
import time
from itertools import cycle
import numpy as np
import pigpio as io
import uli_physik as up

class Flow_sensor(object):
    # Instance properties for the timer/counter background callback function.
    # Number of input impulses counted in a cycle:
    _n_imp = 0
    # Timestamp for first and last input transition in each cycle:
    _t_0, _t_1 = 0.0, 0.0
    
    # Callback for counting and timing flow sensor GPIO input pulses.
    # Called by pi.callback().
    def timer_ctr(self, gpio, level, tick):
        if self._n_imp == 0:
            self._t_0 = tick
        else:
            self._t_1 = tick
        # Anyways:
        self._n_imp += 1

    def __init__(self, pi, flow_conf):
        self.pi = pi
        self.gpio = flow_conf.gpio
        pi.set_mode(self.gpio, io.INPUT)
        pi.set_pull_up_down(self.gpio, io.PUD_UP)
        # Time in seconds for avaraging input pulses
        self.AVG_PERIOD = flow_conf.AVG_PERIOD
        # Sensitivity of the flowmeter channel in pulses per liter
        self.SENSITIVITY = flow_conf.SENS_FLOW
        # Set up a callback function for handling GPIO input pulse timing
        self.timer_counter = pi.callback(
            self.gpio, io.FALLING_EDGE, self.timer_ctr
        )
        self._start_time = time.time()
        # Volumetric coolant flow rate liter/sec
        self._liter_sec = 0.0
        # Default flow sensor temperature for density calculation
        self.temperature = 25.0
        self.density_function = flow_conf.density_function


    @property
    def liter_sec(self):
        t = time.time()
        if t - self._start_time < self.AVG_PERIOD:
            # While averaging time has not passed, return stored value
            return self._liter_sec
        else:
            # Process tally of input pulses and calculate volumetric flow rate
            # in liter/sec
            self._start_time = t
            # Return zero when no pulses were counted
            if self._n_imp == 0:
                return 0.0
            else:
                # Access to global variables is not atomic, thus pause timer
                # during calculateion
                self.timer_counter.cancel()
                self._liter_sec = 1E6*self._n_imp / (
                    self.SENSITIVITY * (self._t_1 - self._t_0)
                )
                # Reset counter
                self._n_imp = 0
               # self.timer_counter.enable()
                self.timer_counter = self.pi.callback(
                    self.gpio, io.FALLING_EDGE, self.timer_ctr
                )
                return self._liter_sec
    @liter_sec.setter
    def liter_sec(self, value):
        raise AttributeError("This is a read-only attribute!")

    @property
    def kg_sec(self):
        return self.liter_sec * self.density_function(self.temperature)
    @kg_sec.setter
    def kg_sec(self, value):
        raise AttributeError("This is a read-only attribute!")


class Measurement(object):
    def __init__(self, ch_conf, pt_pair):
        # Length of moving average filter window
        self.FILTER_SIZE = ch_conf["common"]["FILTER_SIZE"]
        # Reference chanel resistance ratio
        self.N_REF = ch_conf["rref"]["N_REF"]
        # pt_pair[0]: upstream temperature sensor. pt_pair[1]: downstream sensor
        self.info = ch_conf[pt_pair[1]]["info"]
        self.ch_seq = [
              # Resistance reference channel  first,
              ch_conf["rref"]["mux"] << 4
            | ch_conf["common"]["mux"],
              # followed by the upstream temperature sensor, and
              ch_conf[pt_pair[0]]["mux"] << 4
            | ch_conf["rref"]["mux"],
              # completed by the downstream sensor for the current acquisition
              ch_conf[pt_pair[1]]["mux"] << 4
            | ch_conf[pt_pair[0]]["mux"],
        ]
        # Channel offset values are initialized from config file.
        self.offset = [
            ch_conf[key]["offset"] for key in ["rref"] + pt_pair
        ]
        # Measurement channel series (bias-) resistance value
        self.R_S = [ch_conf[key]["R_S"] for key in pt_pair]
        # Platinum RTD base (0°C) resistance calibration values
        self.r_0 = [ch_conf[key]["r_0"] for key in pt_pair]
        # Resistance offset for sensor channel in Ohms
        self.r_offset = [ch_conf[key]["r_offset"] for key in pt_pair]
        # Temperature offset for sensor channel in K
        self.T_offset = ch_conf[pt_pair[1]]["T_offset"]
        self.c_th_function = ch_conf["common"]["c_th_function"]
        # Power offset is set via MQTT
        self.p_offset = 0.0

    # Lock event for critical section; stop event for ordered termination
    def scan_temperatures(self, adc):
        # Buffer for raw input samples.
        # For each measurement channel, four samples are acquired in succession:
        # 1.: resistance reference channel,
        # 2.: upstream Pt1000 sensor, 3.: downstream Pt1000 sensor
        ch_buf = np.zeros((self.FILTER_SIZE, 3), dtype=np.int)

        # From now, update chX_buffer cyclically with new ADC samples and
        # calculate results with averaged data.
        # The following is an endless loop!

        for j in range(0, self.FILTER_SIZE):
            # Do the data acquisition of all multiplexed input channels
            adc.read_continue(self.ch_seq, ch_buf[j])
    
        # Moving average of input samples without offset correction
        self.ch_avg = np.average(ch_buf, axis=0)
        # Elementwise operation (np.array):
        self.ch_unscaled = self.ch_avg - self.offset

        # Calculate resistances for multi-leg wheatstone bridge setup
        # starting with upstream (cold inlet) sensor resistance value
        r_upstream_w_offset = up.wheatstone(
            self.ch_unscaled[1],
            self.ch_unscaled[0],
            self.N_REF,
            self.R_S[0]
        )
        self.r_upstream = r_upstream_w_offset - self.r_offset[0]
        # Downstream sensor uses the upstream sensor as reference bridge leg
        self.r_downstream = up.wheatstone(
            self.ch_unscaled[2],
            # Differential measurement must be added to absolute measurement
            # to calculate the reference voltage for the second bridge setup.
            self.ch_unscaled[1] + self.ch_unscaled[0],
            self.R_S[0]/r_upstream_w_offset,
            self.R_S[1]
        ) - self.r_offset[1]
        # Calculate temperatures from Pt1000 sensor resistances
        # Inverted H.L.Callendar equation for Pt1000 temperatures:
        self.T_upstream = up.ptRTD_temperature(
            self.r_upstream,
            r_0=self.r_0[0]
        )
        self.T_downstream = up.ptRTD_temperature(
            self.r_downstream,
            r_0=self.r_0[1]
        ) - self.T_offset

    def calculate_power(self, flow_kg_sec):
        # Specific heat capacity
        c_th = self.c_th_function(1/2 * (self.T_upstream+self.T_downstream))
        # Final output is thermal power by heat balance calculation
        self.power = flow_kg_sec * c_th * (self.T_downstream-self.T_upstream
                                           ) - self.p_offset
