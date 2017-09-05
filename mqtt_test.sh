#!/bin/sh
# MQTT test script
inject_a(){
	mosquitto_pub -t "ifx1/power" -m "[0.0, 18, 2.7, 3.1, 22, -2.0]"
	mosquitto_pub -t "ifx1/offset" -m "[0.0, 0.1, 0.2, 0.3, 0.4, 0.5]"
	mosquitto_pub -t "ifx1/temp" -m "[20, 21, 22, 23, 24, 25]"
	mosquitto_pub -t "ifx1/flow" -m "0.0044"
}
inject_b(){
	mosquitto_pub -t "ifx1/power" -m "[1.0, 13, 3.7, 2.1, 12, -3.0]"
	mosquitto_pub -t "ifx1/offset" -m "[0.1, 0.2, 0.3, 0.4, 0.5, 0.6]"
	mosquitto_pub -t "ifx1/temp" -m "[21, 22, 23, 24, 25, 26]"
	mosquitto_pub -t "ifx1/flow" -m "0.0034"
}
while /bin/true; do
	inject_a
	sleep 10
	inject_b
	sleep 10
	inject_b
	sleep 10
	inject_a
	sleep 10
	inject_b
	sleep 10
	inject_a
	sleep 10
	inject_a
	sleep 10
done
