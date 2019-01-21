#!/bin/bash

cd /home/steve/temperature_monitoring
sudo echo "Update with git starting now" >> log.txt
sudo python3 fetch_origin_master_with_git.py > /dev/null 2>&1 & 

