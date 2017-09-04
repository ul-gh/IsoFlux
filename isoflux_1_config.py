# -*- coding: utf-8 -*-
import uli_physik
from PiPyADC.ADS1256_definitions import *
####################  IsoFlux MQTT Client CONFIGURATION  #######################
class MQTT(object):
    # Hostname and port of the server which runs the MQTT broker
    HOST = "localhost"
    PORT = 1883
################################################################################

###########################  IsoFlux CONFIGURATION  ############################
# Order in which the heat sources are connected to the coolant supply
flow_sequence = ["cold", "hs_1", "hs_2", "hs_3", "hs_4", "hs_5", ]

# Input channel configuration for the ADC.
CH_CONF = {
    # ADC global setting for all channels
    "common": {
        # PGA gain. Must be one of: (1, 2, 4, 8, 16, 32, 64)
        "gain": 8,
        "mux": NEG_AINCOM,
        # Length of moving average filter window
        "FILTER_SIZE": 16,
#        "FILTER_SIZE": 2,
        # "c_th_function": uli_physik.c_th_water
        "c_th_function": uli_physik.c_th_glykol60,
    },
    "flow": {
        "info": "Flow Meter",
        "mux": NEG_AIN7,
        "offset": 0,
        # Additional averaging filter applied to all samples when updating the
        # sensor channel with new ADC data using the update_avg() method
        "FILTER_SIZE": 4,
        # Sensitivity of flow sensor in liter/sec per volt
        # Wasser: SENS_FLOW = 14.30/1000
        # Glykol-Wasser 60-40: "SENS_FLOW": 15.89/1000
        "SENS_FLOW": 23.71/1000,
        # Density function in terms of temperature in °C for the coolant medium
        # "density_function": uli_physik.rho_water
        "density_function": uli_physik.rho_glykol60,
    },
    # Fixed resistance reference (fixed AVCC divider)
    "rref": {
        "info": "Resistance Reference",
        # Physical input pins of the ADC (MUX register code values):
        "mux": NEG_AIN0,
        # System-level (chip-external) channel ofset (ADC digits).
        "offset": -100,
        # Divider ratio of resistance reference channel N_REF=rs0/r0
        # "N_REF": 9.091800,
        "N_REF": 9.091800,
    },
    # Pt1000 sensor, cold inlet to heat sink #1. Differential voltage
    # measurement relative to the resistance reference channel:
    "cold": {
        "info": "Cold Inlet",
        "mux": NEG_AIN1,
        "offset": 0,
        # Series resistance (bias resistance) of Pt1000 sensor channels in Ohms
        # "R_S": 9962.59,
        "R_S": 9962.00,
        # Platinum RTD base (0°C) resistance calibration values
        # "r_0": 1000.000,
        "r_0": 1000.000,
        # Resistance offset for result channels in Ohms.
        # This accounts for wiring resistance.
        "r_offset": 0.428,
#        "r_offset": 0.000,
        # Temperature offset in K. This accounts for sensor self-heating.
        # This can be left at zero by definition for the cold reference chanel.
        "T_offset": 0.0,
    },
    # The following entries configure the temperature sensors for the heat
    # sources
    "hs_1": {
        "info": "Heat Source 1",
        "mux": NEG_AIN2,
        "offset": 0,
        "R_S": 9960.10,
        "r_0": 1000.055,
        "r_offset": 0.355,
#        "r_offset": 0.000,
        "T_offset": 0.0,
    },
    "hs_2": {
        "info": "Heat Source 2",
        "mux": NEG_AIN3,
        "offset": 0,
        "R_S": 9980.48,
        "r_0": 999.954,
        "r_offset": 0.350,
#        "r_offset": 0.000,
        "T_offset": 0.0,
    },
    "hs_3": {
        "info": "Heat Source 3",
        "mux": NEG_AIN4,
        "offset": 0,
        "R_S": 9974.27,
        "r_0": 1000.100,
        "r_offset": 0.323,
#        "r_offset": 0.000,
        "T_offset": 0.0,
    },
    "hs_4": {
        "info": "Heat Source 4",
        "mux": NEG_AIN5,
        "offset": 0,
        "R_S": 9981.87,
        "r_0": 1000.018,
        "r_offset": 0.270,
#        "r_offset": 0.000,
        "T_offset": 0.0,
    },
    "hs_5": {
        "info": "Heat Source 5",
        "mux": NEG_AIN6,
        "offset": 0,
        "R_S": 9965.30,
        "r_0": 999.936,
        "r_offset": 0.260,
#        "r_offset": 0.000,
        "T_offset": 0.0,
    },
}
################################################################################


###########################  ADC CONFIGURATION  ################################
class ADS1256(object):
    ##############  Raspberry Pi Physical Interface Properties  ################
    # SPI bus configuration and GPIO pins used for the ADS1255/ADS1256.
    # These defaults are used by the constructor of the ADS1256 class.
    #
    # To create multiple class instances for more than one AD converter, a
    # unique configuration must be specified as argument for each instance.
    #
    # The following pins are compatible with
    # the Waveshare High Precision AD/DA board on the Raspberry Pi 2B and 3B
    #
    # SPI_CHANNEL corresponds to the chip select hardware bin controlled by the
    # SPI hardware. For the Waveshare board this pin is not even connected, so
    # this code does not use hardware-controlled CS and this is a don't care.
    # FIXME: Implement hardware chip select as an option.
    SPI_CHANNEL   = 1
    # SPI_MODE specifies clock polarity and phase; MODE=1 <=> CPOL=0, CPHA=1
    SPI_MODE      = 1
    # SPI clock in Hz. The ADS1256 supports a minimum of 1/10th of the output
    # sample data rate in Hz to 1/4th of the oscillator CLKIN_FREQUENCY which
    # results in a value of 1920000 Hz for the Waveshare board. However, since
    # the Raspberry pi only supports power-of-two fractions of the 250MHz system
    # clock, the closest value would be 1953125 Hz, which is slightly out spec
    # for the ADS1256. Choosing 250MHz/256 = 976563 Hz is a safe choice.
    SPI_FREQUENCY = 976563
    # Risking the slightly out-of-spec speed:
    #SPI_FREQUENCY = 1953125

    # The RPI GPIOs used: All of these are optional and must be set to None if
    # not used. In This case, the inputs must be hardwired to the correct logic 
    # level and a sufficient DRDY_TIMEOUT must be specified further below.
    # Obviously, when not using hardware polling of the DRDY signal, acquisition
    # will be much slower with long delays. See datasheet..
    #CS_PIN      = None
    CS_PIN      = 15 
    DRDY_PIN    = 11
    RESET_PIN   = 12
    PDWN_PIN    = 13
    ############################################################################

    ################  ADS1256 Constant Configuration Settings  #################
    # Seconds to wait in case DRDY pin is not connected or the chip
    # does not respond. See table 21 of ADS1256 datasheet: When using a
    # sample rate of 2.5 SPS and issuing a self calibration command,
    # the timeout can be up to 1228 milliseconds:
    DRDY_TIMEOUT    = 2
    # Optional delay in seconds to avoid busy wait and reduce CPU load when
    # polling the DRDY pin. Default is 0.000001 or 1 µs (timing not accurate)
    DRDY_DELAY      = 0.000001
#    DRDY_DELAY      = 0
    # Master clock rate in Hz. Default is 7680000:
    CLKIN_FREQUENCY  = 7680000
    ############################################################################


    # All following settings are accessible through ADS1256 class properties

    ############  ADS1256 Default Runtime Adjustable Properties  ###############
    # Analog reference voltage between VREFH and VREFN pins
    v_ref = 2.5
    # Gain seting of the integrated programmable amplifier. This value must be
    # one of (GAIN_1, GAIN_2, GAIN_4, GAIN_8, GAIN_16, GAIN_32, GAIN_64).
    # Gain=4, V_ref=2.5V ==> 24-bit two's complement full-scale input <=> 1,25V
    gain_flags = int.bit_length(CH_CONF["common"]["gain"]) - 1
    ############################################################################

    ##################  ADS1256 Default Register Settings  #####################
    # REG_STATUS:
    # When enabling the AUTOCAL flag: Any following operation that changes
    # PGA GAIN, DRATE or BUFFER flags triggers a self calibration:
    # THIS REQUIRES an additional timeout via WaitDRDY() after each such
    # operation.
    status = BUFFER_ENABLE
    # REG_MUX:
    # Default: positive input = AIN0, negative input = AINCOM
    mux = POS_AIN0 | NEG_AINCOM
    # REG_ADCON:
    # Disable clk out signal (not needed, source of disturbance),
    # sensor detect current sources disabled, gain setting as defined above:
    adcon = CLKOUT_OFF | SDCS_OFF | gain_flags
    # REG_DRATE: 
    # 10 SPS places a filter zero at 50 Hz and 60 Hz for line noise rejection
    drate  = DRATE_50
#    drate  = DRATE_100
    # REG_IO: No GPIOs needed
    gpio = 0x00
################################################################################
