#! /usr/bin/python3.5

import datetime
import glob
import MySQLdb
import subprocess

base_dir = '/sys/bus/w1/devices/'          # Location of 1 wire devices in the file system

log_to_console = True

def app_version():
    return ("v0.10 27/01/19")


def setup_db_connection(caller, host, db, user, passwd):
    write_to_log(caller, "cf: >> setup_db_connection()")
    
    try:
        db = MySQLdb.connect(host, user, passwd, db)
    except:
        write_to_log(caller, "***Database connection failed!")
        db = None
    write_to_log(caller, "cf: << setup_db_connection()")
    return db


def write_to_log(caller, text_to_write):
    #global Global_dict
    logging = "true"

    if caller == "web":
        log_file = "weblog.txt"
    elif caller == "temps":
        log_file = "log.txt"
    else:
        log_file = "log.txt"

    #if Global_dict is not None:
    #    if Global_dict['write_to_logfile'] == "true":
    #        logging = "true"
    #else:
    #    logging = "true"

    if logging == "true":
        try:
            logfile =  open(log_file, 'a+')
            now = datetime.datetime.now()
            log_date = str(now.day) + "/"+ str(now.month).zfill(2) + "/" + str(now.year) + " " + str(now.hour).zfill(2) + ":" + str(now.minute).zfill(2) + ":" + str(now.second).zfill(2) + " "
            log_string = log_date + " " + text_to_write
            
            logfile.write(log_string + "\n")
            if log_to_console == True:
                print(log_string)
                
            logfile.close()
        except:
            print("Failed to open " + log_file + " for writing")


def get_local_ip_address(caller):
    write_to_log(caller, "cf: >> get_local_ip_address()")

    ip_address = None
    ps = subprocess.Popen(['ifconfig'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
        outbytes = subprocess.check_output(('grep', '-A 1', 'wlan0'), stdin=ps.stdout)
        output = str(outbytes)
        #print(output)
        find_start_of_ip = output[output.find('inet ')+5:len(output)]
        ip_address = find_start_of_ip[0:find_start_of_ip.find(' ')]
        write_to_log(caller, "cf:   IP Address: " + ip_address)
        #time.sleep(1)
    except subprocess.CalledProcessError:
        # grep did not match any lines
        write_to_log(caller, "cf: ERROR    No wireless networks connected!!")
        #time.sleep(5)
    
    write_to_log(caller, "cf: << get_local_ip_address()")
    return ip_address


def check_table_exists(caller, db_cursor, table_name):
    write_to_log(caller, "cf:   Checking whether the " + table_name + " table already exists")

    table_check = "SHOW TABLES LIKE '%" + table_name + "%'"
    db_cursor.execute(table_check)
    #print("Rows returned: " + str(cursor.rowcount))
    return db_cursor.fetchone()                         # this will be None for none existent table


def check_wireless_network_connection(caller):
    write_to_log(caller, "cf: >> check_wireless_network_connection()")
    ssid = ''
    quality = 0
    level = 0
    result = None

    ps = subprocess.Popen(['iwconfig'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
        outbytes = subprocess.check_output(('grep', 'off/any'), stdin=ps.stdout) #this will fail if connected!!
        
    except subprocess.CalledProcessError:
        # this means there was a network found as 'off/any' only occurs when not connected
        ps = subprocess.Popen(['iwconfig'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        outbytes = subprocess.check_output(('grep', 'ESSID'), stdin=ps.stdout)
        output = str(outbytes)
        find_start_of_ssid = output[output.find('ESSID:')+7:len(output)]
        ssid = find_start_of_ssid[0:find_start_of_ssid.find('"')]
        result = True
        write_to_log(caller, "cf:   WiFi SSID: " + ssid)
        result = 0
    
    if result is not None:    
        ps = subprocess.Popen(['iwconfig'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        outbytes = subprocess.check_output(('grep', 'Quality'), stdin=ps.stdout)
        output = str(outbytes)
        pos = output.find('Quality=')
        quality_str = output[pos+len('Quality='):len(output)]
        quality_str = quality_str[0:2]
        quality = int((float(quality_str) / 70.0) * 100.0)
        write_to_log(caller, "cf:   WiFi Signal quality: " + str(quality) + "%")
    
        pos = output.find('Signal level=')
        level_str = output[pos+len('Signal level='):len(output)]
        level_str = level_str[0:3]
        level = int(level_str)
        write_to_log(caller, "cf:   WiFi Signal Level: " + str(level) + "dBm")
    else:
        write_to_log(caller, "cf: ***** No wireless network connection")
        
    write_to_log(caller, "cf: << check_wireless_network_connection()")
    return ssid, quality, level


def find_all_temp_sensors_connected(caller):
    all_sensors_list = []
    devices = glob.glob(base_dir + '28*')
    write_to_log(caller, "cf: >> find_all_temp_sensors_connected()")
    count = 0
    if len(devices):
        write_to_log(caller, "cf:   " + str(len(devices)) + " sensor(s) found:")
        for count, sensor in enumerate(devices):
            sensor_name = sensor.strip()[-15:]
            write_to_log(caller, "cf:     " + sensor.strip()[-15:])
        
            all_sensors_list.append(sensor_name)
    else:
        write_to_log(caller, "cf:   No Sensors found!")
        all_sensors_list = None      
    write_to_log(caller, "cf: << find_all_temp_sensors_connected()")
    return all_sensors_list

