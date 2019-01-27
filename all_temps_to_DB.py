#!/usr/bin/python3.5

import datetime
import os
import glob
from pathlib import Path
import time
import MySQLdb
import RPi.GPIO as GPIO
import signal
import smtplib
import socket
import subprocess
import sys
import time

#Setup for 1 Wire Temp Probe etc...
#os.system('modprobe w1-gpio')              # load one wire communication device kernel modules
#os.system('modprobe w1-therm')

database_name = "temps"
database_user_name = "temps_user"
database_password = "user"

log_to_console = True

email_user = "moc.liamg@2791rednesliame.ipyrrebpsar"
email_passwd = "!P4yrrebpsaR"

Global_db_cursor = None
Global_db_conn = None
Global_dict = None
Global_logfile = None

base_dir = '/sys/bus/w1/devices/'          # Location of 1 wire devices in the file system


def setup_gpio():
    GPIO.setmode(GPIO.BCM)   #Use GPIO no, NOT pin no
    GPIO.setup(18, GPIO.OUT)
    GPIO.setup(23, GPIO.OUT)
    GPIO.setup(24, GPIO.OUT)
    GPIO.output(18, False)
    GPIO.output(23, False)
    GPIO.output(24, False)


def network_status(status):
    GPIO.output(18, status)


def expected_sensor_count(status):
    GPIO.output(23, status)


def safe_to_unplug(status):
    GPIO.output(24, status)


def write_to_log(text_to_write):
    global Global_dict
    logging = "false"
    
    if Global_dict is not None:
        if Global_dict['write_to_logfile'] == "true":
            logging = "true"
    else:
        logging = "true"
        
    if logging == "true":
        try:
            logfile =  open('log.txt', 'a')
            now = datetime.datetime.now()
            log_date = str(now.day) + "/"+ str(now.month).zfill(2) + "/" + str(now.year) + " " + str(now.hour).zfill(2) + ":" + str(now.minute).zfill(2) + ":" + str(now.second).zfill(2) + " "
            log_string = log_date + " " + text_to_write
            
            logfile.write(log_string + "\n")
            if log_to_console == True:
                print(log_string)
                
            logfile.close()
        except:
            print("Failed to open log.txt for writing")


def clean_old_log_file():
    now = datetime.datetime.now()
    log_date = str(now.day) + str(now.month).zfill(2) + str(now.year) + "_" + str(now.hour).zfill(2) + str(now.minute).zfill(2)
    logs_dir = Path("/home/steve/temperature_monitoring/logs")
    log_file = Path("/home/steve/temperature_monitoring/log.txt")
    if log_file.is_file():   
        # log file exists
        #print("log file exists")
        os.system("gzip -q log.txt")
        if logs_dir.is_dir():
            #print("found logs dir")
            os.system("mv -f log.txt.gz logs/log_" + log_date + ".gz")
        else:
            #print("making logs dir")
            os.system("mkdir logs")
            os.system("mv -f log.txt.gz logs/log_" + log_date + ".gz")


def signal_handler(sig, frame):
    write_to_log("\n")
    write_to_log("***********  Received Signal " + str(sig) + " shutting down\n")
    clean_shutdown()


def clean_shutdown():
    write_to_log("Cleanly closing the Database")
    if Global_db_cursor is not None:
        Global_db_cursor.close()
    if Global_db_conn is not None:
        Global_db_conn.close()
    network_status(False)
    expected_sensor_count(False)
    safe_to_unplug(True)
    write_to_log("Finished....")
    sys.exit(0)


def find_all_temp_sensors_connected():
    all_sensors_list = []
    devices = glob.glob(base_dir + '28*')
    write_to_log(">> find_all_temp_sensors_connected()")
    count = 0
    if len(devices):
        write_to_log("   " + str(len(devices)) + " sensor(s) found:")
        for count, sensor in enumerate(devices):
            sensor_name = sensor.strip()[-15:]
            write_to_log("     " + sensor.strip()[-15:])
        
            all_sensors_list.append(sensor_name)
    else:
        write_to_log("   No Sensors found!")
        all_sensors_list = None      
    write_to_log("<< find_all_temp_sensors_connected()")
    return all_sensors_list


def find_temp_sensor_pos(sensor_id):
    devices = glob.glob(base_dir + '28*')
    #print("Looking for sensor: " + str(sensor_id) + ", in folder " + base_dir)
    count = 0
    for count, sensor in enumerate(devices):
        pos = sensor.find(sensor_id)
        if pos is not -1:
            #print("Found sensor in " + sensor + ", this is sensor " + str(count))
            return count
            
    return None


def read_temp_raw(sensor_id):
    write_to_log(">> read_temp_raw()")
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
    write_to_log("<< read_temp_raw()")
    return lines


def read_temp(sensor_id):
    write_to_log(">> read_temp(" + sensor_id + ")")
    lines = read_temp_raw(sensor_id)
    if lines is None:
        write_to_log("   lines is None!!!")
        return None

    retry_counter = 1
    max_retries = 3
    
    while lines[0].strip()[-3:] != 'YES' and retry_counter < max_retries: # ignore first line
        time.sleep(0.2)
        lines = read_temp_raw(sensor_id)
        retry_counter += 1
        
    if lines[0].strip()[-3:] == 'YES':
        equals_pos = lines[1].find('t=')                    # find temperature in the details
    else:
        write_to_log("   Sensor not returning valid temperature / it may have been unplugged!")
        return None

    if equals_pos != -1:
        temp_string = lines[1][equals_pos+2:]
        temp_c = round(float(temp_string) / 1000.0, 1)      # convert to Celsius and round to 1 decimal place
        write_to_log("   returning non-corrected temperature of " + str(temp_c))
        write_to_log("<< read_temp()")
        return temp_c
    write_to_log("<< read_temp()")


def setup_db_connection(host, db, user, passwd):
    write_to_log(">> setup_db_connection()")

    try:
        db = MySQLdb.connect(host, user, passwd, db)
    except:
        write_to_log("***Database connection failed!")
        db = None
    write_to_log("<< setup_db_connection()")
    return db


def check_table_exists(db_cursor, table_name):
    write_to_log("   Checking whether the " + table_name + " table already exists")

    table_check = "SHOW TABLES LIKE '%" + table_name + "%'"
    db_cursor.execute(table_check)
    #print("Rows returned: " + str(cursor.rowcount))
    return db_cursor.fetchone()                         # this will be None for none existent table


def create_temp_readings_table(db_cursor):
    write_to_log("   Creating table for temperature readings")
    sql = """CREATE TABLE TEMP_READINGS (
             temp_id INT NOT NULL AUTO_INCREMENT,
             date_added DATETIME NOT NULL,
             temp_sensor_db_id INT,
             temperature FLOAT NOT NULL,
             PRIMARY KEY (temp_id) )"""
    if db_cursor.execute(sql):
        return None
    else:
        return 0


def create_sensors_table(db_conn, db_cursor):
    write_to_log("   Creating table for temperature sensors")
    sql = """CREATE TABLE TEMP_SENSORS (
             sensor_id INT NOT NULL AUTO_INCREMENT,
             date_added DATETIME NOT NULL,
             temp_sensor_id CHAR(15) NOT NULL,
             temp_sensor_alias VARCHAR(50),
             temp_offset FLOAT NOT NULL,
             connected BOOLEAN NOT NULL,
             PRIMARY KEY (sensor_id) )"""

    db_cursor.execute(sql)
    sql = """INSERT INTO TEMP_SENSORS (date_added, temp_sensor_id, temp_sensor_alias, temp_offset, connected) 
             VALUES (NOW(), '28-020691770d70', 'Ambient 0d70', 0, 0), 
             (NOW(), '28-020b917749e4', 'Monitor 49e4', -0.7, 0), 
             (NOW(), '28-02069177144d', 'Wired 144d', -0.8, 0), 
             (NOW(), '28-0118679408ff', 'Bare 08ff', -0.4, 0), 
             (NOW(), '28-020a9177f3c4', 'Raspberry PI f3c4', -1.1, 0), 
             (NOW(), '28-020891777a83', 'Wired 7a83', -0.7, 0)"""
    try:
        db_cursor.execute(sql)
        db_conn.commit()
        write_to_log("   TEMP_SENSORS table updated OK")
    except:
        db_conn.rollback()
        write_to_log("   TEMP_SENSORS table update failed!!")
        return None
    return 0


def delete_sensors_table(db_conn, db_cursor):
    write_to_log("   Deleting all entries in the sensors table")
    sql = "DROP TABLE TEMP_SENSORS"
             
    try:
        db_cursor.execute(sql)
        db_conn.commit()
        write_to_log("   TEMP_SENSORS table deleted OK")
        return 0
    except:
        db_conn.rollback()
        write_to_log("   TEMP_SENSORS table delete failed!!")
        return None


def manage_settings_db_and_dict_stuff(db_conn, db_cursor):
    write_to_log(">> manage_settings_db_stuff()")
    
    result = check_table_exists(db_cursor, "TEMP_APP_SETTINGS")
    if result is None:
        write_to_log("*** NO TEMP_APP_SETTINGS Table")
        if create_settings_table(db_conn, db_cursor) is None:
            clean_shutdown()
    else:
        write_to_log("   OK - TEMP_APP_SETTINGS table exists")

    existing, added = check_for_settings_for_defaults_and_updates(db_conn, db_cursor)
    if existing is None:
        clean_shutdown()
    else:
        write_to_log("   " + str(existing) + " settings already existed")
        write_to_log("   " + str(added) + " settings added")

    global Global_dict
    Global_dict = settings_db_to_dictionary(db_cursor)
    
    write_to_log("<< manage_settings_db_stuff()")
    return None


def create_settings_table(db_conn, db_cursor):
    write_to_log("   Creating table for settings")
    sql = """CREATE TABLE TEMP_APP_SETTINGS (
             settings_id INT NOT NULL AUTO_INCREMENT,
             name CHAR(50) NOT NULL,
             value CHAR(50) NOT NULL,
             last_updated DATETIME NOT NULL,
             PRIMARY KEY (settings_id) )"""

    try:
        db_cursor.execute(sql)
        db_conn.commit()
        write_to_log("   TEMP_APP_SETTINGS table created OK")
    except:
        db_conn.rollback()
        write_to_log("   TEMP_APP_SETTINGS table creation failed!!")
        return None

    return 0


def check_for_settings_for_defaults_and_updates(db_conn, db_cursor):
    write_to_log(">> check_for_settings_for_defaults_and_updates()")
    
    settings = [('sensor_polling_freq', '300'),
                ('write_to_logfile', 'true'),
                ('start_up_status_email', 'false'),
                ('first_read_settle_time', '30'),
                ('email_recipient_addr', 'moc.liamg@draws.rednef')]
    
    no_of_settings = len(settings)
    settings_added = 0
    settings_existing = 0
    
    for setting in settings:
        setting, value = setting
        query = "SELECT name FROM temps.TEMP_APP_SETTINGS WHERE name = '" + setting + "'"
        db_cursor.execute(query)
        if db_cursor.rowcount == 0:
            insert_sql = "INSERT INTO TEMP_APP_SETTINGS (name, value, last_updated) VALUES ('" + setting + "', '" +  value + "', NOW())"
            try:
                db_cursor.execute(insert_sql)
                db_conn.commit()
                write_to_log("   ADDED: Setting:  " + setting + "   Value: " + value)
                settings_added += 1
            except:
                db_conn.rollback()
                write_to_log("   TEMP_APP_SETTINGS table update failed!!")
                return None, None
        else:
            settings_existing += 1
            #write_to_log("   EXISTS: Setting:  " + setting + "   Value: " + value)
            
    write_to_log("<< check_for_settings_for_defaults_and_updates()")    
    return settings_existing, settings_added

    
def settings_db_to_dictionary(db_cursor):
    write_to_log(">> settings_db_to_dictionary")
    write_to_log("     Fetching settings from DB --> Dictionary")
    dictionary = {}
    
    query = "SELECT name, value FROM TEMP_APP_SETTINGS"
    db_cursor.execute(query)
    
    for row in db_cursor.fetchall():
        write_to_log("       Setting: " + str(row[0]) + " = " + str(row[1]))
        dictionary[str(row[0])] = str(row[1])
    write_to_log("<< settings_db_to_dictionary")
    return dictionary


def write_temp_reading_to_db(db_conn, db_cursor, db_sensor_id, temp_reading):
    write_to_log(">> write_temp_reading_to_db()")
    temp_reading = round(temp_reading, 1) 
    sql = "INSERT INTO TEMP_READINGS (date_added, temp_sensor_db_id, temperature) VALUES (NOW(), '" + str(db_sensor_id) + "', " + str(temp_reading) + ")"

    try:
        db_cursor.execute(sql)
        #print(db_cursor.execute(sql))
        db_conn.commit()
        write_to_log("   Temp including offset - " + str(temp_reading) + " added OK")
    except:
        db_conn.rollback()
        write_to_log("   Temp reading add failed!!")
    write_to_log("<< write_temp_reading_to_db()")


def reset_sensor_connected_status(db_conn, db_cursor):
    write_to_log(">> reset_sensor_connected_status()")
    try:
        update_sql = "UPDATE temps.TEMP_SENSORS SET connected = 0 WHERE sensor_id > 0"
        db_cursor.execute(update_sql)
        db_conn.commit()
        write_to_log("   reset sensor connected status for all OK")
    except:
        db_conn.rollback()
        write_to_log("   reset sensor connected status update failed!!")
        # do something else here!?!?!?!
        return None;
    return 0;
    write_to_log("<< reset_sensor_connected_status()")
    return id, temp_offset


def find_temp_sensor_id_and_offset(db_conn, db_cursor, sensor_id):
    write_to_log(">> find_temp_sensor_id_and_offset()")
    query = "SELECT * FROM temps.TEMP_SENSORS WHERE temp_sensor_id = '" + sensor_id + "'"
    db_cursor.execute(query)
    id = None
    temp_offset = 0
    write_to_log("   Looking for sensor id: " + sensor_id)
    for row in db_cursor.fetchall():
        id = str(row[0])
        date = str(row[1])
        temp_sensor_id = str(row[2])
        temp_sensor_alias = row[3]
        temp_offset = row[4]
        write_to_log("   Sensor info from DB: " + id + " " + date + " " + temp_sensor_id + " " + str(temp_offset))
        try:
            update_sql = "UPDATE temps.TEMP_SENSORS SET connected = 1 WHERE temp_sensor_id='" + temp_sensor_id + "'"
            db_cursor.execute(update_sql)
            db_conn.commit()
            write_to_log("   updated sensor connected status for " + temp_sensor_id)
        except:
            db_conn.rollback()
            write_to_log("   sensor connected status update failed for " + temp_sensor_id + "!!")
            # do something else here!?!?!?!
        
    if id is None:
        write_to_log("***Sensor info not found in DB***")
    write_to_log("<< find_temp_sensor_id_and_offset()")
    return id, temp_offset


def dump_all_db_data_out(db_cursor):
    query = "SELECT * FROM temps.TEMP_READINGS"
    db_cursor.execute(query)
    write_to_log("Current database contents for TEMP_READINGS......")
    for row in db_cursor.fetchall():
        id = str(row[0])
        date = str(row[1])
        temp_sensor_db_id = str(row[2])
        temp_sensor_id = str(row[2])
        temp = str(row[4])
        write_to_log(id + " " + date + " " + temp_sensor_db_id + " " + temp_sensor_id + " " + temp)


def check_wireless_network_connection():
    write_to_log(">> check_wireless_network_connection()")
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
        write_to_log("   WiFi SSID: " + ssid)
        result = 0
    
    if result is not None:    
        ps = subprocess.Popen(['iwconfig'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        outbytes = subprocess.check_output(('grep', 'Quality'), stdin=ps.stdout)
        output = str(outbytes)
        pos = output.find('Quality=')
        quality_str = output[pos+len('Quality='):len(output)]
        quality_str = quality_str[0:2]
        quality = int((float(quality_str) / 70.0) * 100.0)
        write_to_log("   WiFi Signal quality: " + str(quality) + "%")
    
        pos = output.find('Signal level=')
        level_str = output[pos+len('Signal level='):len(output)]
        level_str = level_str[0:3]
        level = int(level_str)
        write_to_log("   WiFi Signal Level: " + str(level) + "dBm")
    else:
        write_to_log("***** No wireless network connection")
        
    write_to_log("<< check_wireless_network_connection()")
    return ssid, quality, level


def get_local_ip_address():
    write_to_log(">> get_local_ip_address()")

    ip_address = None
    ps = subprocess.Popen(['ifconfig'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
        outbytes = subprocess.check_output(('grep', '-A 1', 'wlan0'), stdin=ps.stdout)
        output = str(outbytes)
        #print(output)
        find_start_of_ip = output[output.find('inet ')+5:len(output)]
        ip_address = find_start_of_ip[0:find_start_of_ip.find(' ')]
        write_to_log("   IP Address: " + ip_address)
        #time.sleep(1)
    except subprocess.CalledProcessError:
        # grep did not match any lines
        write_to_log("ERROR    No wireless networks connected!!")
        #time.sleep(5)
    
    write_to_log("<< get_local_ip_address()")
    return ip_address


def send_email(user, pwd, recipient, subject, body):
    write_to_log(">> send_email()")
    FROM = user
    TO = recipient if isinstance(recipient, list) else [recipient]
    SUBJECT = subject
    TEXT = body

    # Prepare actual message
    message = "From: %s\nTo: %s\nSubject: %s\n\n%s" % (FROM, ", ".join(TO), SUBJECT, TEXT)
    
    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        status = server.ehlo()
        write_to_log("       ehlo:  " + str(status))
        status = server.starttls()
        write_to_log("   starttls:  " + str(status))
        status = server.login(user, pwd)
        write_to_log(" user login:  " + str(status))
        server.sendmail(FROM, TO, message)
        server.close()
        write_to_log(" email sent OK")
    except:
        write_to_log("****** failed to send email!!")

    write_to_log("<< send_email()")

#############################################################################################################

def do_main():
    global Global_db_conn
    global Global_db_cursor
    global Global_dict
    global send_start_up_status_email
    safe_to_unplug(True)
    all_sensors_list = None
    write_to_log("------------------------    Checking Network Connection OK   ------------------------")

    ssid, quality, level = check_wireless_network_connection()
    if ssid == '':
        sys.exit(0)

    ip_address = get_local_ip_address()
    
    network_status(True)
    
    write_to_log("------------------------    Checking Database Connection OK   -----------------------")

    db_conn = setup_db_connection("localhost", database_name, database_user_name, database_password)
    if db_conn is None:
        write_to_log("ERROR  - DB connection failed!")
        clean_shutdown()
    else:
        write_to_log("   DB connection OK")

    cursor = db_conn.cursor()
    Global_db_conn = db_conn
    Global_db_cursor = cursor

    #Setup a Query
    #query = "SELECT * FROM test.temps WHERE date_of_reading < STR_TO_DATE('24/12/2018 17:00', '%d/%m/%Y %H:%i') "
    safe_to_unplug(False)
    
    manage_settings_db_and_dict_stuff(db_conn, cursor)

    result = check_table_exists(cursor, "TEMP_READINGS")
    if result is None:
        write_to_log("*** NO TEMP_READINGS Table")
        if create_temp_readings_table(cursor) is None:
            clean_shutdown()
    else:
        write_to_log("   OK - TEMP_READINGS table exists")

    result = check_table_exists(cursor, "TEMP_SENSORS")
    if result is None:
        write_to_log("*** NO TEMP_SENSORS Table")
        if create_sensors_table(db_conn, cursor) is None:
            clean_shutdown()
    else:
        write_to_log("   OK - TEMP_SENSORS table exists")

    write_to_log("-------------------    Finished DB connection and setup all OK   -------------------")

    safe_to_unplug(True)
    result = reset_sensor_connected_status(db_conn, cursor)
    if result is None:
        write_to_log("ERROR - sensor connection status reset failed!")
        if create_sensors_table(db_conn, cursor) is None:
            clean_shutdown()

    while all_sensors_list is None:
        all_sensors_list = find_all_temp_sensors_connected()
        if all_sensors_list is None:
            write_to_log("***Waiting 5 seconds before trying again")
            time.sleep(5)

    no_of_sensors = len(all_sensors_list)
    if no_of_sensors == 3:
        expected_sensor_count(True)
    else:
        expected_sensor_count(False)

    send_start_up_status_email = Global_dict['start_up_status_email']
    #Override for start emails!
    send_start_up_status_email = "false"

    if send_start_up_status_email == "true":
        send_email(email_user[::-1], email_passwd[::-1], Global_dict['email_recipient_addr'][::-1], 
               "PI Temperature Monitoring Power Up Status", 
               "\nConnected WiFi network: " + ssid + "  -  OK\n\nInitial startup and checking of DB  -  OK\n\n" + 
               "Temperature Sensors detected:  "+ str(len(all_sensors_list)) + "\n\n\nHome page:\nhttp://" + ip_address + 
               ":5000/home\n                       or\nhttp://" + socket.gethostname() + ".local:5000/home\n\n")
    
    settle_time = int(Global_dict['first_read_settle_time'])
    write_to_log("Waiting %d seconds for the initial readings" % settle_time)
    time.sleep(settle_time)

    while True:
        ssid, quality, level = check_wireless_network_connection()
        if ssid != '':
            network_status(True)
        else:
            network_status(False)
            
        all_sensors_list = find_all_temp_sensors_connected()
        no_of_sensors = len(all_sensors_list)
        if no_of_sensors == 3:
            expected_sensor_count(True)
        else:
            expected_sensor_count(False)
                   
        for sensor_name in all_sensors_list:
            db_sensor_id, offset = find_temp_sensor_id_and_offset(db_conn, cursor, sensor_name)      
            write_to_log("   DB Sensor ID: " + str(db_sensor_id) + "   Temp Offset: " + str(offset))
            safe_to_unplug(False)
            if db_sensor_id is not None:
                temperature = read_temp(sensor_name)
                if temperature is not None:
                    write_temp_reading_to_db(db_conn, cursor, db_sensor_id, (temperature + offset))
                else:
                    write_to_log("***Unable to obtain temperature reading! Return from call was None")
            else:
                write_to_log("***No info for sensor " + sensor_name + ", ignoring! Temp is " + str(read_temp(sensor_name)))
        loop_time = int(Global_dict['sensor_polling_freq'])
        write_to_log("The next reading will be taken in " + str(int(round(loop_time / 60, 0))) + " minutes")
        print("\n-----------   Temperature Sensor Readings Taken, Now Waiting for loop time   --------\n")
        safe_to_unplug(True)
        time.sleep(loop_time)
        os.system('clear')
    else:
        write_to_log("***No sensor db id found, exiting")
    #dump_all_db_data_out(cursor)

########################################################################################################

#Setup Handler for catching ctrl+c and kill signal, then shutdown cleanly
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)
setup_gpio()
os.system('clear')
clean_old_log_file()
write_to_log("\n\n************  Started  -  all_temps_to_DB.py  ************\n")
do_main()
