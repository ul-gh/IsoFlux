#!/usr/bin/python
# -*- coding: utf-8 -*-
#  IsoFlux sensor definition
from itertools import cycle
import numpy as np
import uli_physik as up

class Flow_sensor(object):
    def __init__(self, adc, ch_conf):
        FILTER_SIZE_FLOW = ch_conf["flow"]["FILTER_SIZE"]
        FILTER_SIZE_COMMON = ch_conf["common"]["FILTER_SIZE"]
        self.info = ch_conf["flow"]["info"]
        self.channel = ch_conf["flow"]["mux"]<<4 | ch_conf["common"]["mux"]
        self.offset = ch_conf["flow"]["offset"]
        self.v_per_digit = adc.v_ref*2.0/(ch_conf["common"]["gain"]*(2**23-1))
        # Sensitivity of the flowmeter channel in liter per second per volt
        self.SENSITIVITY = ch_conf["flow"]["SENS_FLOW"]
        self.density_function = ch_conf["flow"]["density_function"]
        self.samples = np.zeros(FILTER_SIZE_FLOW)
        self.avg_cycle = cycle(range(0, FILTER_SIZE_FLOW))
        # Now initializing with data acquired from the ADC
        # adc.mux is a Python @property setting the respecitve ADC register
        adc.mux = self.channel
        adc.sync()
        for i in range(0, FILTER_SIZE_FLOW):
            avg = 0.0
            for j in range(0, FILTER_SIZE_COMMON):
                avg += adc.read_and_next_is(self.channel)
            self.samples[i] = avg/FILTER_SIZE_COMMON - self.offset
        self.voltage = np.average(self.samples) * self.v_per_digit
        # Volumetric coolant flow rate liter/sec
        self.liter_sec = self.voltage * self.SENSITIVITY

    def set_temperature(self, temperature):
        self.temperature = temperature

    def update(self, unscaled_sample):
        # Update sample buffer. Index using an iterator function.
        self.samples[self.avg_cycle.next()] = unscaled_sample
        self.voltage = np.average(self.samples) * self.v_per_digit
        # Volumetric coolant flow rate liter/sec
        self.liter_sec = self.voltage * self.SENSITIVITY
        self.kg_sec = self.liter_sec * self.density_function(self.temperature)


class Measurement(object):
    def __init__(self, ch_conf, pt_pair):
        # Length of moving average filter window
        self.FILTER_SIZE = ch_conf["common"]["FILTER_SIZE"]
        # Reference chanel resistance ratio
        self.N_REF = ch_conf["rref"]["N_REF"]
        # pt_pair[0]: upstream temperature sensor. pt_pair[1]: downstream sensor
        self.info = ch_conf[pt_pair[1]]["info"]
        self.ch_seq = [
              # Flow sensor channel first,
              ch_conf["flow"]["mux"] << 4
            | ch_conf["common"]["mux"],
              # resistance reference channel next,
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
            ch_conf[key]["offset"] for key in ["flow", "rref"] + pt_pair
        ]
        # Measurement channel series (bias-) resistance value
        self.R_S = [ch_conf[key]["R_S"] for key in pt_pair]
        # Platinum RTD base (0°C) resistance calibration values
        self.r_0 = [ch_conf[key]["r_0"] for key in pt_pair]
        # Resistance offset for sensor channel in Ohms
        self.r_offset = [ch_conf[key]["r_offset"] for key in pt_pair]
        self.c_th_function = ch_conf["common"]["c_th_function"]
        # Power offset is set via MQTT
        self.p_offset = 0.0

    # Lock event for critical section; stop event for ordered termination
    def scan_temperatures(self, adc):
        # Buffer for raw input samples.
        # For each measurement channel, four samples are acquired in succession:
        # 1.: flow sensor, 2.: resistance reference,
        # 3.: upstream Pt1000 sensor, 4.: downstream Pt1000 sensor
        ch_buf = np.zeros((self.FILTER_SIZE, 4), dtype=np.int)

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
        self.r_upstream = up.wheatstone(
            self.ch_unscaled[2],
            self.ch_unscaled[1],
            self.N_REF,
            self.R_S[0]
        ) - self.r_offset[0]
        # Downstream sensor uses the upstream sensor as reference bridge leg
        self.r_downstream = up.wheatstone(
            self.ch_unscaled[3],
            # Differential measurement must be added to absolute measurement
            # to calculate the reference voltage for the second bridge setup.
            self.ch_unscaled[2] + self.ch_unscaled[1],
            self.R_S[0]/self.r_upstream,
            self.R_S[1]
        ) - self.r_offset[1]
        # Calculate temperatures from Pt1000 sensor resistances
        # Inverted H.L.Callendar equation for Pt1000 temperatures:
        self.T_upstream = up.ptRTD_temperature(self.r_upstream,r_0=self.r_0[0])
        self.T_downstream = up.ptRTD_temperature(self.r_downstream,
                                                 r_0=self.r_0[1]
                                                 )

    def calculate_power(self, flow_kg_sec):
        # Specific heat capacity
        c_th = self.c_th_function(1/2 * (self.T_upstream+self.T_downstream))
        # Final output is thermal power by heat balance calculation
        self.power = flow_kg_sec * c_th * (self.T_downstream-self.T_upstream
                                           ) - self.p_offset

