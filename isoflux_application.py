#!/usr/bin/python
# -*- coding: utf-8 -*-
"""IsoFlux Heat Balance Calorimetry System

This is the application controller normally launched at system start via
/etc/systemd/system/isoflux.service file.

2017-09-03 Ulrich Lukas
"""
import sys
import time
import threading
from isoflux_mqtt import IFX_MQTT
from isoflux import IsoFlux
import isoflux_1_config

# Lock for critical sections, stop event for ordered termination of all threads
thread_lock = threading.Lock()
thread_stop = threading.Event()

try:
    print(
        "\033[2J\033[H\033[?25l" # Clear screen, hide cursor
        "{}{}\n" # Output info
        "Press ENTER to exit. "
        "Press 'z' + ENTER for performing a zero-calibration"
        "{}{}{}".format( # Reserve scroll buffer space
            __doc__,
            IsoFlux.__doc__,
            "\n"*30,
            "\033M"*30,
            "\033[J",
        )
    )

    # IsoFlux instance is doing all measurement data acquisition
    isoflux_1 = IsoFlux(isoflux_1_config)

    # IsoFlux MQTT client interface for communication with the NodeRed GUI
    ifx1_mqtt = IFX_MQTT(thread_lock, thread_stop, isoflux_1, topic="ifx1")

    # Thread 1: MQTT client interface
    t_ifx1_mqtt = threading.Thread(target=ifx1_mqtt.client_start, args=())
    # Since the MQTT server waits indefinitely for incoming connections, the
    # daemon flag is set for automatic termination when the main thread exits.
    t_ifx1_mqtt.daemon = 1
    t_ifx1_mqtt.start()

    sys.stdout.write("Connecting to MQTT client interface... ")
    ctr = 0
    while not ifx1_mqtt.isConnected:
        ctr += 1
        time.sleep(0.1)
        sys.stdout.write(".")
        if ctr > 600:
            raise IOError("Timeout while trying to connect!")
    sys.stdout.write("\n")

    # Thread 2: IsoFlux measurement
    t_do_measurement = threading.Thread(
        target=isoflux_1.do_measurement,
        args=(thread_lock, thread_stop)
    )
    t_do_measurement.start()

    time.sleep(1)
    while True:
        # The following is the textmode interface:
        if raw_input() == 'z':
            thread_lock.acquire()
            print(
                "\033[H\033[2J" # Clear screen
                "\n"*4 + "Zero-Calibration...\n"
                "Old offset:   {}\n"
                "Sensor values: {}".format(
                    " ".join(["0.0"] + ["{: 12.3f}".format(i.T_offset)
                                        for i in isoflux_1.measurements
                                        ]
                    ),
                    " ".join(
                        ["{: 12.3f}".format(i) for i in isoflux_1.temperature]
                    ),
                )
            )
            # This sets the output power levels to zero:
            for i in isoflux_1.measurements:
                i.T_offset += i.T_downstream - i.T_upstream
            print(
                  "New offset:    "
                + " ".join(["0.0"] + ["{: 12.3f}".format(i.T_offset)
                                      for i in isoflux_1.measurements
                                      ]
                )
            )
            raw_input("Press ENTER to continue!")
            print(
                "\033[H\033[2J" # Clear screen
                "Press ENTER to exit.\n"
                "Press 'z' + ENTER for performing a zero-calibration\n\n"
                "\033[s" # Store cursor position
            )
            thread_lock.release()
        else:
            # Stop all threads and exit
            thread_stop.set()
            t_do_measurement.join()
            # t_srv_http is marked as a daemon thread and needs no termination.
            print(
                "\n"*6 + "User exit.\n"
                "\033[?25h\033[0m" # Reset cursor and color
            )
            sys.exit(0)

except (KeyboardInterrupt, SystemExit):
    thread_stop.set()
    t_do_measurement.join()
    # t_srv_http is marked as a daemon thread and needs no termination.
    print("{}Exit.\n\033[?25h\033[0m".format("\n"*10)) # Reset cursor and color
    sys.exit(0)
