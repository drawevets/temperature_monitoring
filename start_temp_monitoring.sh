#!/bin/bash

cd /home/steve/Python_Code/temperature_monitoring
sudo echo "About to run: All_Temp_Sensors_To_DB.py" >> log.txt
sudo python3 All_Temp_Sensors_To_DB.py > /dev/null 2>&1 & 
