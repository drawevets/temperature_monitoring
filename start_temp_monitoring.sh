#!/bin/bash

cd /home/steve/Python_Code/temperature_monitoring
sudo echo "Start Script: About to run - All_Temp_Sensors_To_DB.py" >> log.txt
sudo python3 all_temp_to_DB.py > /dev/null 2>&1 & 
