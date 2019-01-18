#!/bin/bash

cd /home/steve/Python_Code/temperature_monitoring
sudo echo "now starting code" >> log.txt
sudo python3 All_Temp_Sensors_To_DB.py >> log.txt 2>&1 & 
