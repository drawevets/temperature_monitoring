#!/bin/bash
start_time=$(date +'%m/%d/%Y %T')

cd /home/steve/temperature_monitoring
sudo echo "${start_time}: Update with git starting now" >> /home/steve/temperature_monitoring/update_log.txt
sudo python3 fetch_origin_master_with_git.py >> /home/steve/temperature_monitoring/update_log.txt & 
end_time=$(date +'%m/%d/%Y %T')
sudo echo "${end_time}: Finished update check / complete update" >> /home/steve/temperature_monitoring/update_log.txt

