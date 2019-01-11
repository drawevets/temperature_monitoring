#!/usr/bin/python3.5
#Comment added to test out the working of git!!


import os
import glob
import time
import MySQLdb
import sys
import signal
import subprocess

#Setup for 1 Wire Temp Probe etc...
#os.system('modprobe w1-gpio')                              # load one wire communication device kernel modules
#os.system('modprobe w1-therm')

database_name = "test"
database_user_name = "steve"
database_password = "db_passwd"

Global_db_cursor = None
Global_db_conn = None

loop_time = 5 * 60                                         # loop time in seconds
base_dir = '/sys/bus/w1/devices/'                          # point to the address


def find_all_temp_sensors_connected():
    all_sensors_list = []
    devices = glob.glob(base_dir + '28*')
    print(">> find_all_temp_sensors_connected()")
    count = 0
    if len(devices):
        print("   " + str(len(devices)) + " sensor(s) found:")
        for count, sensor in enumerate(devices):
            sensor_name = sensor.strip()[-15:]
            print("     " + sensor.strip()[-15:])
        
            all_sensors_list.append(sensor_name)
    else:
        print("   No Sensors found!")
        all_sensors_list = None      
    print("<< find_all_temp_sensors_connected()")
    return all_sensors_list


def find_temp_sensor_pos(sensor_id):
    #print("  >> find_temp_sensor_pos()")
    devices = glob.glob(base_dir + '28*')
    print("     Looking for sensor: " + str(sensor_id) + ", in folder " + base_dir)
    count = 0
    for count, sensor in enumerate(devices):
        pos = sensor.find(sensor_id)
        if pos is not -1:
            print("     Found sensor in " + sensor + ", this is sensor " + str(count))
            print("  << find_temp_sensor_pos()") 
            return count
        else:
            print("     Not found in " + sensor + ", this is sensor " + str(count))
    #print("  << find_temp_sensor_pos()")            
    return None


def read_temp_raw(sensor_id):
    #print(" >> read_temp_raw()")
    if sensor_id is not None:
        pos = find_temp_sensor_pos(sensor_id)
        if pos is not None:
            #print("Sensor position in list is " + str(pos))
            device_folder = glob.glob(base_dir + '28*')[pos]
        else:
            return None
    else:
        device_folder = glob.glob(base_dir + '28*')[0]      # find device with address starting from 28*
    device_file = device_folder + '/w1_slave'
    f = open(device_file, 'r')
    lines = f.readlines()                                   # read the device details
    f.close()
    #print(" << read_temp_raw()")
    return lines


def read_temp(sensor_id):
    #print(">> read_temp()")
    lines = read_temp_raw(sensor_id)
    if lines is None:
        print("   lines is None!!!")
        return None
    while lines[0].strip()[-3:] != 'YES':                   # ignore first line
        time.sleep(0.2)
        lines = read_temp_raw(sensor_id)

    if lines[0].strip()[-3:] == 'YES':
        equals_pos = lines[1].find('t=')                    # find temperature in the details
    else:
        print("   Sensor not returning valid temperature / it may have been unplugged!")
        return None

    if equals_pos != -1:
        temp_string = lines[1][equals_pos+2:]
        temp_c = round(float(temp_string) / 1000.0, 1)      # convert to Celsius and round to 1 decimal place
        print("   returning non-corrected temperature of " + str(temp_c))
        print("<< read_temp()")
        return temp_c
    #print("<< read_temp()")

#############################################################################################################

def main():

    all_sensors_list = None

    while True:
        all_sensors_list = None       
        while all_sensors_list is None:
            all_sensors_list = find_all_temp_sensors_connected()
            if all_sensors_list is None:
                print("***Waiting 5 seconds before trying again")
                time.sleep(5)
        time.sleep(1)
    
        for sensor_name in all_sensors_list:
            temperature = read_temp(sensor_name)
            if temperature is not None:
                print("Temperature for sensor " + sensor_name + " is " + str(temperature))
            else:
                print("***Unable to obtain temperature reading! Return from call was None")

        time.sleep(10)
        os.system('clear')
        

########################################################################################################

os.system('clear')
main()
