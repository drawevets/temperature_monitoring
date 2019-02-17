#! /usr/bin/python3.5

import datetime
import glob
import MySQLdb
import os
from pathlib import Path
import platform
import re
import subprocess
import time

base_dir = '/sys/bus/w1/devices/'          # Location of 1 wire devices in the file system

log_to_console = True

def app_version():
    return ("v0.127 - Last updated: 14/02/19")


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


def clean_old_log_file():
    now = datetime.datetime.now()
    log_date = str(now.day) + str(now.month).zfill(2) + str(now.year) + "_" + str(now.hour).zfill(2) + str(now.minute).zfill(2)
    logs_dir = Path("/home/steve/temperature_monitoring/logs")
    log_file = Path("/home/steve/temperature_monitoring/weblog.txt")
    if log_file.is_file():   
        # log file exists
        os.system("gzip -q weblog.txt")
        if logs_dir.is_dir():
            #print("found logs dir")
            os.system("mv -f weblog.txt.gz logs/weblog_" + log_date + ".gz")
        else:
            #print("making logs dir")
            os.system("mkdir logs")
            os.system("mv -f weblog.txt.gz logs/weblog_" + log_date + ".gz")


def clear_log_archive(caller):
    write_to_log(caller, "cf: >> clear_log_archive()")
    logs_dir = "/home/steve/temperature_monitoring/logs"
    logs_dir_path = Path(logs_dir)

    if logs_dir_path.is_dir():
        write_to_log(caller, "cf:   logs directory exists, attempting to rm it!")
        os.system("rm -rf " + logs_dir)
        
    write_to_log(caller, "cf: << clear_log_archive()")


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


def find_temp_sensor_pos(caller, sensor_id):
    devices = glob.glob(base_dir + '28*')
    #print("Looking for sensor: " + str(sensor_id) + ", in folder " + base_dir)
    count = 0
    for count, sensor in enumerate(devices):
        pos = sensor.find(sensor_id)
        if pos is not -1:
            #print("Found sensor in " + sensor + ", this is sensor " + str(count))
            return count
            
    return None


def find_temp_sensor_id_alias_and_offset(caller, db_conn, db_cursor, sensor_id, update_conn_status):
    write_to_log(caller, "cf: >> find_temp_sensor_id_and_offset()")
    query = "SELECT * FROM temps.TEMP_SENSORS WHERE temp_sensor_id = '" + sensor_id + "'"
    db_cursor.execute(query)
    id = None
    temp_offset = 0
    write_to_log(caller, "cf:   Looking for sensor id: " + sensor_id)
    for row in db_cursor.fetchall():
        id = str(row[0])
        date = str(row[1])
        temp_sensor_id = str(row[2])
        temp_sensor_alias = row[3]
        temp_offset = row[4]
        write_to_log(caller, "cf:   Sensor info from DB: " + id + " " + date + " " + temp_sensor_alias + " " + temp_sensor_id + " " + str(temp_offset))
        if update_conn_status is True:
            try:
                update_sql = "UPDATE temps.TEMP_SENSORS SET connected = 1 WHERE temp_sensor_id='" + temp_sensor_id + "'"
                db_cursor.execute(update_sql)
                db_conn.commit()
                write_to_log(caller, "cf:   updated sensor connected status for " + temp_sensor_id)
            except:
                db_conn.rollback()
                write_to_log(caller, "cf:   sensor connected status update failed for " + temp_sensor_id + "!!")
                # do something else here!?!?!?!
        
    if id is None:
        write_to_log(caller, "cf:***Sensor info not found in DB***")
    write_to_log(caller, "cf: << find_temp_sensor_id_and_offset()")
    return id, temp_sensor_alias, temp_offset


def get_all_connected_sensor_ids(caller, db_cursor):
    write_to_log(caller, "cf: >> get_all_connected_sensor_ids()")
    query = "SELECT sensor_id FROM temps.TEMP_SENSORS WHERE connected = '1'"
    db_cursor.execute(query)
    sensor_ids = []
    write_to_log(caller, "   Sensors currently connected:")
    for row in db_cursor.fetchall():
        write_to_log(caller, str(row[0]))
        sensor_ids.append(str(row[0]))
        
    write_to_log(caller, sensor_ids)
    write_to_log(caller, "cf: << get_all_connected_sensor_ids()")
    return sensor_ids


def get_filesystem_stats(caller):
    write_to_log(caller, "cf: >> get_filesystem_stats()")
    statvfs = os.statvfs('/')
    total_capacity = round(statvfs.f_frsize * statvfs.f_blocks / (1024*1024*1024), 3)
    free_space = round(statvfs.f_frsize * statvfs.f_bfree / (1024*1024*1024), 3)
    disk_used = round( ((statvfs.f_frsize * statvfs.f_blocks) - (statvfs.f_frsize * statvfs.f_bfree)) / (1024*1024*1024), 3)
    write_to_log(caller, "   Total capacity = " + str(total_capacity) + "   Free space = " + str(free_space))
    write_to_log(caller, "cf: << get_filesystem_stats()")
    return total_capacity, free_space, disk_used
    

def get_last_temperature_reading_from_db(caller, db_cursor, sensor_id):
    reading_date = None
    temperature = None
    temp_sensor_alias = None
    temp_sensor_id = None
    
    write_to_log(caller, "cf: >> get_last_temperature_reading_from_db()")
    query = """SELECT CONCAT(LPAD(DAY(TEMP_READINGS.date_added),2,'0'), '/',LPAD(MONTH(TEMP_READINGS.date_added),2,'0'), '/',YEAR(TEMP_READINGS.date_added),' ',
                             LPAD(HOUR(TEMP_READINGS.date_added),2,'0'),':',LPAD(MINUTE(TEMP_READINGS.date_added),2,'0')) as time_added, 
                      temperature, 
                      TEMP_SENSORS.temp_sensor_alias,
                      TEMP_SENSORS.temp_sensor_id
               FROM temps.TEMP_READINGS 
               JOIN TEMP_SENSORS ON temp_sensor_db_id = TEMP_SENSORS.sensor_id
               WHERE temp_sensor_db_id = """ + sensor_id + " ORDER BY temp_id DESC LIMIT 1"
    no_rows = db_cursor.execute(query)
    for row in db_cursor.fetchall():
        reading_date = str(row[0])
        temperature = str(row[1])
        temp_sensor_alias = str(row[2])
        temp_sensor_id = str(row[3])
        
    return reading_date, temperature, temp_sensor_alias, temp_sensor_id
    write_to_log(caller, "cf: << get_last_temperature_reading_from_db()")


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


def get_size_of_directory(caller, directory):
    dir_path = Path(directory)
    sizemb = 0
    
    if dir_path.is_dir():
        cmd = ["du", "-sh", "-b", directory]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        tmp = str(proc.stdout.read())
        size = (re.findall('\d+', tmp)[0])
        sizemb = round(int(size)/(1024*1024), 3)
        write_to_log(caller, "   Size of " + directory + " is " + str(sizemb) + "MB")
    return sizemb


def get_size_of_file(caller, file_to_check):
    file_path = Path(file_to_check)
    sizemb = 0
    
    if file_path.is_file():
        cmd = ["du", "-sh", "-b", file_to_check]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        tmp = str(proc.stdout.read())
        size = (re.findall('\d+', tmp)[0])
        sizemb = round(int(size)/(1024*1024), 3)
        write_to_log(caller, "   Size of " + file_to_check + " is " + str(sizemb) + "MB")
    return sizemb
    

def get_system_information():
    os = platform.system()
    architecture = platform.machine()
    oskernel = platform.platform()
    firmwareversion = platform.version()

    with open('/proc/uptime', 'r') as f:
        uptime_seconds = float(f.readline().split()[0])
        uptime_string = str(datetime.timedelta(seconds = uptime_seconds))[0:-7]

    return os, architecture, oskernel, firmwareversion, uptime_string


def read_temp(caller, sensor_id):
    write_to_log(caller, "cf: >> read_temp(" + sensor_id + ")")
    lines = read_temp_raw(caller, sensor_id)
    if lines is None:
        write_to_log(caller, "cf:   lines is None!!!")
        return None

    retry_counter = 1
    max_retries = 3
    
    while lines[0].strip()[-3:] != 'YES' and retry_counter < max_retries: # ignore first line
        time.sleep(0.2)
        lines = read_temp_raw(caller, sensor_id)
        retry_counter += 1
        
    if lines[0].strip()[-3:] == 'YES':
        equals_pos = lines[1].find('t=')                    # find temperature in the details
    else:
        write_to_log(caller, "cf:    Sensor not returning valid temperature / it may have been unplugged!")
        return None

    if equals_pos != -1:
        temp_string = lines[1][equals_pos+2:]
        temp_c = round(float(temp_string) / 1000.0, 1)      # convert to Celsius and round to 1 decimal place
        write_to_log(caller, "cf:    returning non-corrected temperature of " + str(temp_c))
        write_to_log(caller, "cf: << read_temp()")
        return temp_c
    write_to_log(caller, "cf: << read_temp()")


def read_temp_raw(caller, sensor_id):
    write_to_log(caller, "cf: >> read_temp_raw()")
    if sensor_id is not None:
        pos = find_temp_sensor_pos(caller, sensor_id)
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
    write_to_log(caller, "cf: << read_temp_raw()")
    return lines


def reset_db_table(caller, table_to_reset):
    write_to_log(caller, "cf: >> reset_db_table()")
    
    result = False
    
    #                                         Location      DB Name  DB Username   DB Passwd
    tmp_db_conn = setup_db_connection(caller, "localhost",  "temps", "temps_admin", "admin",)

    if tmp_db_conn is None:
        write_to_log(caller, "cf:   DB connection failed!")
        return result
    else:
        write_to_log(caller, "cf:   DB connection OK")

    tmp_db_conn_cursor = tmp_db_conn.cursor()

    check = check_table_exists(caller, tmp_db_conn_cursor, table_to_reset)
    if check is not None:
        write_to_log(caller, "cf:   Truncating " + table_to_reset + " table")
        tmp_db_conn_cursor.execute("TRUNCATE TABLE " + table_to_reset)
        tmp_db_conn.commit()
        write_to_log(caller, "cf:   Table truncated OK")
        result = True
    else:
        write_to_log(caller, "cf:   Table does not exist!")

    tmp_db_conn_cursor.close()
    tmp_db_conn.close()

    write_to_log(caller, "cf: << reset_db_table()")
    return result


def setup_db_connection(caller, host, db, user, passwd):
    write_to_log(caller, "cf: >> setup_db_connection()")
    
    try:
        db = MySQLdb.connect(host, user, passwd, db)
    except:
        write_to_log(caller, "***Database connection failed!")
        db = None
    write_to_log(caller, "cf: << setup_db_connection()")
    return db

def update_sensor_display_name(caller, sensor_uid, new_name):
    write_to_log(caller, "cf: >> update_sensor_display_name()")
    
    result = False
    #                                         Location      DB Name  DB Username   DB Passwd
    tmp_db_conn = setup_db_connection(caller, "localhost",  "temps", "temps_admin", "admin",)

    if tmp_db_conn is None:
        write_to_log(caller, "cf:   DB connection failed!")
        return result
    else:
        write_to_log(caller, "cf:   DB connection OK")

    tmp_db_conn_cursor = tmp_db_conn.cursor()

    try:
        update_sql = "UPDATE temps.TEMP_SENSORS SET temp_sensor_alias = '" + new_name + "' WHERE temp_sensor_id='" + sensor_uid + "'"
        write_to_log(caller, "cf:   "+ update_sql)
        tmp_db_conn_cursor.execute(update_sql)
        tmp_db_conn.commit()
        write_to_log(caller, "cf:   updated sensor display name for " + sensor_uid)
        result = True
    except:
        tmp_db_conn.rollback()
        write_to_log(caller, "cf:   sensor name update failed for " + sensor_uid + "!!")

    tmp_db_conn_cursor.close()
    tmp_db_conn.close()

    write_to_log(caller, "cf: << update_sensor_display_name()")
    return result


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
            log_date = str(now.day).zfill(2) + "/"+ str(now.month).zfill(2) + "/" + str(now.year) + " " + str(now.hour).zfill(2) + ":" + str(now.minute).zfill(2) + ":" + str(now.second).zfill(2) + " "
            log_string = log_date + " " + text_to_write
            
            logfile.write(log_string + "\n")
            if log_to_console == True:
                print(log_string)
                
            logfile.close()
        except:
            print("Failed to open " + log_file + " for writing")


def write_to_last_change_file(caller, reason):
        try:
            change_file =  open("/home/steve/temperature_monitoring/last_change.txt", 'w+')
            now = datetime.datetime.now()
            log_date = str(now.day).zfill(2) + "/"+ str(now.month).zfill(2) + "/" + str(now.year) + " " + str(now.hour).zfill(2) + ":" + str(now.minute).zfill(2) + ":" + str(now.second).zfill(2) + " "
            log_string = log_date + " " + reason
            change_file.write(log_string + "\n")
            change_file.close()
        except:
            print("Failed to write to /home/steve/temperature_monitoring/last_change.txt")
