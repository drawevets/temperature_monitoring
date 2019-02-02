#!/bin/bash

cd /home/steve/temperature_monitoring
sudo echo "Start Script: About to run - temps_manage_reading.py" >> log.txt
sudo python3 temps_manage_reading.py > /dev/null 2>&1 & 
sudo echo "Start Script: About to run - temps_flask.py" >> log.txt
sudo python3 temps_flask.py > /dev/null 2>&1 &

