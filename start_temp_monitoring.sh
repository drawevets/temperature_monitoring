#!/bin/bash

cd /home/steve/temperature_monitoring
sudo echo "Start Script: About to run - All_Temp_Sensors_To_DB.py" >> log.txt
sudo python3 all_temps_to_DB.py > /dev/null 2>&1 & 
cd Flask
sudo python3 flask_demo2.py > /dev/null 2>&1 &

