#!/usr/bin/python
# -*- coding: utf-8 -*-
import sys
import time
# import threading
import numpy as np
import uli_physik as up
from PiPyADC.pipyadc import ADS1256
import isoflux_sensors
import isoflux_1_config

class IsoFlux(object):
    """IsoFlux - Quasi-Isothermal Heat Balance Calorimetry

    Thermal power measurement for engineering application performing
    heat flux balance of device under test with constant flow rate coolant
    fluid.
    
    Quasi-isothermal condition is achieved by implementing a millikelvin-
    precision differential temperature measurement with platinum resistive
    temperature sensors in a deflection-type bridge configuration.
    
    By performing the measurement with heat exchanger and coolant
    temperature set approximately at environmental level, convection and
    radiation heat loss is negligible for power electronics application.
    
    Hardware: 2x ADS1256 24-Bit 8-ch low-noise ADC interfaced to the
              Raspberry Pi via SPI. Analog frontend currently using the
              Waveshare "High-Precision AD/DA Board".
         
    Coolant fluid circuit must be series-connected such that the hot
    outlet of each heat source is fed into the cold inlet of the next
    following heat source with negligible heat loss. 
    The order of the measurement channels can be configured in config file.
    
    Ulrich Lukas 2017-09-03
    """
    
    def __init__(self, conf):
        # Coolant flow through the sensors must be in this order
        self.flow_sequence = conf.flow_sequence
        # Number of channels
        self.n_ch = len(self.flow_sequence)

        # Initialise ADC
        self.adc = ADS1256(conf.ADS1256)
        self.adc.cal_self()

        # Flow sensor class has volumetric and gravimetric flow as properties
        # which are updated indirectly with ADC samples via the update() method.
        # Coolant temperature must be set via the set_temperature method.
        self.flow_sensor = isoflux_sensors.Flow_sensor(self.adc, conf.CH_CONF)

        # For each measurement, we need one upstream and one downstream coolant
        # temperature Pt1000 sensor. This is a list of lists.
        pt_pairs = [self.flow_sequence[n-1:n+1] for n in range(1, self.n_ch)]

        # Results in measurements[i].power etc.
        self.measurements = [isoflux_sensors.Measurement(conf.CH_CONF, pt_pair)
                             for pt_pair in pt_pairs
                             ]
        # These class properties store the measurement results of interest for
        # the main application. Values for the coolant cold influx channel are
        # also stored at index zero. Other channel indices are offset by one.
        self.info = [conf.CH_CONF["cold"]["info"]] + [
            i.info for i in self.measurements
        ]
        self.resistance = np.zeros(self.n_ch)
        self.temperature = np.zeros(self.n_ch)
        # Influx sensor by definition has no power reading, self.power[0] stays
        # at zero and is stored to keep indexing identical for all channels.
        self.power = np.zeros(self.n_ch)
        # Power offset is set via MQTT
        self.p_offset = np.zeros(self.n_ch)


    def scan_all(self):
        # Scanning all measurement channels
        for i, measurement in enumerate(self.measurements):
            measurement.scan_temperatures(self.adc)
            # To calculate the mass flow rate of the fluid, its temperature
            # at the flow meter must be known. Flow meter is by definition
            # mounted upstream of the first measurement sensor, thus i == 0
            if i == 0:
                # Special treatment of first measurement in order to store the
                # coolant influx (cold channel) sensor values. Influx sensor by
                # definition has no power reading, self.power[0] stays at zero.
                self.resistance[0] = measurement.r_upstream
                self.temperature[0] = measurement.T_upstream
                # Influx temperature is also needed for determining the mass
                # flow rate from volumetric flow measurement.
                self.flow_sensor.set_temperature(measurement.T_upstream)
            # Update flow rate value using ADC data acquired with every
            # temperature scan
            self.flow_sensor.update(measurement.ch_unscaled[0])
            # When gravimetric flow rate is known, thermal power is calculated
            measurement.calculate_power(self.flow_sensor.kg_sec)
            # Because self.[resistance|power|temperature][0] stores the coolant
            # cold upstream sensor values, indices for the active measurement
            # channels are offset by one.
            i += 1
            self.resistance[i] = measurement.r_downstream
            self.temperature[i] = measurement.T_downstream
            self.power[i] = measurement.power
            measurement.p_offset = self.p_offset[i]



    # Lock event for critical section; stop event for ordered termination
    def do_measurement(self, thread_lock=None, thread_stop=None):
        print("Number of heat measurement channels configured: {}"
              "".format(len(self.measurements))
              )
        print("Output values averaged over {} ADC samples."
              "".format(self.measurements[0].FILTER_SIZE)
              )
        # Time stamp to limit output data rate to fixed time interval
        timestamp = time.time()
        toggle_color = True

        while True:
            # Stop operation when requested
            if thread_stop is not None:
                if thread_stop.isSet():
                    break
            self.scan_all()
            elapsed = time.time() - timestamp
            if elapsed > 1:
                timestamp += 1
                # Command line output. Threading lock is necessary for unclut-
                # tered text output in case other threads also write to stdout
                if thread_lock is not None:
                    thread_lock.acquire()
                # For calibration use the following instead:
                self.cal_output()
#                self.nice_output()
                if thread_lock is not None:
                    thread_lock.release()


    # Format nice looking text output:
    _n_o_firstrun = True
    _n_o_toggle = True
    def nice_output(self):
        #return # DEBUG: Unclutter output
        # First run: Store console cursor position and set up static variable.
        if self._n_o_firstrun is True:
            self._n_o_firstrun = False
            sys.stdout.write("\033[s") # Store cursor position
        # Toggle color:
        self._n_o_toggle = self._n_o_toggle!=True
        if self._n_o_toggle is True:
            sys.stdout.write("\033[31m")
        else:
            sys.stdout.write("\033[0m")

        sys.stdout.write(
            "Mass flow rate: {: 6.3f} g/sec ({: 6.3f} ml/sec). "
            "Sensor voltage: {: 6.3f} V\033[J\n\n"
            # Output sensor values and restore cursor position:
            "{}\033[u".format(
                1000*self.flow_sensor.kg_sec, 1000*self.flow_sensor.liter_sec,
                self.flow_sensor.voltage,
                # List of strings concatenated by join() method of empty string:
                "".join(
                    [
                        "Channel: {} \n"
                        "Resistance: {: 8.3f} Ohms, Temperature: {: 7.3f} °C, "
                        "Power: {: 5.3f} J/s\033[J\n\n".format(
                            self.info[i],
                            self.resistance[i], self.temperature[i],
                            self.power[i]
                        ) for i in range(0, self.n_ch)
                    ]
                )
            )
        )
        sys.stdout.flush()


    # Extended output for calibration purposes:
    def cal_output(self):
        sys.stdout.write("\033[2J\033[H") # Clear screen

        pt_channels_raw = [i.ch_avg[2] for i in self.measurements]
        pt_channels_raw.append(self.measurements[-1].ch_avg[3])
        pt_channels_oc = [i.ch_unscaled[2] for i in self.measurements]
        pt_channels_oc.append(self.measurements[-1].ch_unscaled[3])

        sys.stdout.write(
            "Channel: Flow. Raw value: {: 10d}\n"
            "Mass flow rate: {: 6.3f} g/sec ({: 6.3f} ml/sec). "
            "Sensor voltage: {: 6.3f} V\033[J\n\n"
            "Channel: R_ref. Raw value: {: 10d}\033[J\n\n"
            "{}".format(
                int(self.flow_sensor.voltage / self.flow_sensor.v_per_digit),
                1000*self.flow_sensor.kg_sec,
                1000*self.flow_sensor.liter_sec,
                self.flow_sensor.voltage,
                int(self.measurements[0].ch_avg[1]),
                # List of strings concatenated by the string.join() method:
                "".join(
                    [
                        "Channel: {}. Raw value: {: 10d}. "
                        "Offset Zeroed: {: 10d}\n"
                        "Resistance: {: 8.3f} Ohms, Temperature: {: 7.3f} °C, "
                        "Power: {: 5.3f} J/s"
                        "\033[J\n\n".format(
                            self.info[i], int(pt_channels_raw[i]),
                            int(pt_channels_oc[i]),
                            self.resistance[i],
                            self.temperature[i],
                            self.power[i]
                        ) for i in range(0, self.n_ch)
                    ]
                )
            )
        )
        sys.stdout.flush()



# This module can be run standalone w/o the MQTT remote interface
if __name__ == "__main__":
    try:
        print(
            "\033[2J\033[H\033[?25l" # Clear screen, hide cursor
            "{}{}{}{}Press CTRL-C to exit.\n".format(
                IsoFlux.__doc__,
                "\n"*28, "\033M"*28, "\033[J\n", # Reserve scroll buffer space
            )
        )
        isoflux_1 = IsoFlux(isoflux_1_config)
        isoflux_1.do_measurement()

    except (KeyboardInterrupt):
        print("\033[J\nUser exit.\n\033[?25h")
        sys.exit(0)


