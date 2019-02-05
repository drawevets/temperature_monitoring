#!/bin/bash

echo "********************* ${EMAIL_SENDING_ACCOUNT} email sending account ****************" >> log.txt
cd /home/steve/temperature_monitoring
echo "Start Script: About to run - temps_manage_reading.py" >> log.txt
python3 temps_manage_reading.py > /dev/null 2>&1 & 
echo "Start Script: About to run - temps_flask.py" >> log.txt
python3 temps_flask.py > /dev/null 2>&1 &

