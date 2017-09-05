# -*- coding: utf-8 -*-
import time
import sys
from subprocess import call
import json
import paho.mqtt.client as mqtt
import isoflux_1_config as conf

class IFX_MQTT(object):
    """IsoFlux MQTT client interface

    2017-09-03 Ulrich Lukas
    """
    def __init__(self, thread_lock, thread_stop, isoflux, topic="ifx1"):
        self.thread_lock = thread_lock
        self.thread_stop = thread_stop
        self.isoflux = isoflux
        self.topic = topic 
        self.isConnected = False

    def tare_channel(self, client, ch):
        if not 0 < ch < len(self.isoflux.p_offset):
            raise IndexError("Channel number out of range")
        self.thread_lock.acquire()
        print(
            "\033[H\033[2J\n\n\n" #Clear screen
            "{} MQTT interface requested Zero-Calibration for channel HS{:d}.\n"
            "Old offset:    {: 12.3f}\n"
            "Sensor values: {: 12.3f}".format(
                self.topic, ch,
                self.isoflux.p_offset[ch],
                self.isoflux.power[ch],
            )
        )
        # This sets the output power levels to zero:
        self.isoflux.p_offset[ch] += self.isoflux.power[ch]
        # Publish updated state value:
        client.publish(
            "{}/offset".format(self.topic),
            json.dumps(self.isoflux.p_offset.tolist())
        )
        print(
            "New offset:    {: 12.3f}\n"
            "Local terminal: Press ENTER to exit. "
            "Press 'z' + ENTER for all-channel zero-calibration\n\n\n"
            "\033[s".format( # ANSI command, store cursor position
                self.isoflux.p_offset[ch]
            )
        )
        self.thread_lock.release()
 
    def set_offset(self, client, ch, new_offset):
        if not 0 <= ch < len(self.isoflux.p_offset):
            raise IndexError("Channel number out of range")
        self.isoflux.p_offset[ch] = new_offset
        client.publish(
            "{}/offset".format(self.topic),
            json.dumps(self.isoflux.p_offset.tolist())
        )

    def on_connect(self, client, userdata, flags, rc):
        print("OK {} MQTT connection established.".format(self.topic))
        client.subscribe("{}/control/#".format(self.topic))
        if rc == 0:
            self.isConnected = True
        else:
            raise IOError("Could not connect to MQTT client")
            

    def on_message(self, client, userdata, msg):
        # Partition topic string after header:
        action = msg.topic[len("{}/control/".format(self.topic)):]

        if action == "poweroff":
            if msg.payload == "OK":
                self.thread_lock.acquire()
                print("Poweroff requested...")
                self.thread_stop.set()
                call(["shutdown", "-h", "now"])

        elif action == "tare":
            channel = int(msg.payload)
            self.tare_channel(client, channel)

        elif action.startswith("set_offsets/"):
            channel = int(action[len("set_offsets/"):])
            self.set_offset(client, channel, float(msg.payload))

    def client_start(self):
        client = mqtt.Client()
        client.on_connect = self.on_connect
        client.on_message = self.on_message

        client.connect(conf.MQTT.HOST, conf.MQTT.PORT, 60)
        client.loop_start()

        while True:
            if self.thread_stop.isSet():
                break
            # Publish IsoFlux data state update every two seconds:
            time.sleep(2)
            client.publish(
                "{}/power".format(self.topic),
                json.dumps(self.isoflux.power.tolist())
            )
            client.publish(
                "{}/offset".format(self.topic),
                json.dumps(self.isoflux.p_offset.tolist())
            )
            client.publish(
                "{}/temp".format(self.topic),
                json.dumps(self.isoflux.temperature.tolist())
            )
            client.publish(
                "{}/flow".format(self.topic),
                self.isoflux.flow_sensor.kg_sec
            )
