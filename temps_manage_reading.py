#!/usr/bin/python3.5

import email_config
import common_functions as cfuncs
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

email_user = email_config.email_details['sender_addr']
email_passwd = email_config.email_details['sender_passwd']
email_recipient_addr = email_config.email_details['recipient']

lg = "temps"

Global_db_cursor = None
Global_db_conn = None
Global_dict = None
Global_logfile = None

last_change_string = None

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
    cfuncs.write_to_log(lg, "\n")
    cfuncs.write_to_log(lg, "***********  Received Signal " + str(sig) + " shutting down\n")
    clean_shutdown()


def clean_shutdown():
    cfuncs.write_to_log(lg, "Cleanly closing the Database")
    if Global_db_cursor is not None:
        Global_db_cursor.close()
    if Global_db_conn is not None:
        Global_db_conn.close()
    network_status(False)
    expected_sensor_count(False)
    safe_to_unplug(True)
    cfuncs.write_to_log(lg, "Finished....")
    sys.exit(0)


def create_temp_readings_table(db_cursor):
    cfuncs.write_to_log(lg, "   Creating table for temperature readings")
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
    cfuncs.write_to_log(lg, "   Creating table for temperature sensors")
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
             (NOW(), '28-0118679408ff', 'Bare 08ff', -0.7, 0), 
             (NOW(), '28-020a9177f3c4', 'Raspberry PI f3c4', -1.1, 0), 
             (NOW(), '28-020891777a83', 'Wired 7a83', -0.7, 0),
             (NOW(), '28-0118677269ff', 'Bare 09ff', -0.9, 0)"""
    try:
        db_cursor.execute(sql)
        db_conn.commit()
        cfuncs.write_to_log(lg, "   TEMP_SENSORS table created and updated OK")
    except:
        db_conn.rollback()
        cfuncs.write_to_log(lg, "   TEMP_SENSORS table update failed!!")
        return None
    return 0


def delete_sensors_table(db_conn, db_cursor):
    cfuncs.write_to_log(lg, "   Deleting all entries in the sensors table")
    sql = "DROP TABLE TEMP_SENSORS"
             
    try:
        db_cursor.execute(sql)
        db_conn.commit()
        cfuncs.write_to_log(lg, "   TEMP_SENSORS table deleted OK")
        return 0
    except:
        db_conn.rollback()
        cfuncs.write_to_log(lg, "   TEMP_SENSORS table delete failed!!")
        return None


def manage_settings_db_and_dict_stuff(db_conn, db_cursor):
    cfuncs.write_to_log(lg, ">> manage_settings_db_stuff()")
    
    result = cfuncs.check_table_exists(lg, db_cursor, "TEMP_APP_SETTINGS")
    if result is None:
        cfuncs.write_to_log(lg, "*** NO TEMP_APP_SETTINGS Table")
        if create_settings_table(db_conn, db_cursor) is None:
            clean_shutdown()
    else:
        cfuncs.write_to_log(lg, "   OK - TEMP_APP_SETTINGS table exists")

    existing, added = check_for_settings_for_defaults_and_updates(db_conn, db_cursor)
    if existing is None:
        clean_shutdown()
    else:
        cfuncs.write_to_log(lg, "   " + str(existing) + " settings already existed")
        cfuncs.write_to_log(lg, "   " + str(added) + " settings added")

    global Global_dict
    Global_dict = settings_db_to_dictionary(db_cursor)
    
    cfuncs.write_to_log(lg, "<< manage_settings_db_stuff()")
    return None


def create_settings_table(db_conn, db_cursor):
    cfuncs.write_to_log(lg, "   Creating table for settings")
    sql = """CREATE TABLE TEMP_APP_SETTINGS (
             settings_id INT NOT NULL AUTO_INCREMENT,
             name CHAR(50) NOT NULL,
             value CHAR(50) NOT NULL,
             last_updated DATETIME NOT NULL,
             PRIMARY KEY (settings_id) )"""

    try:
        db_cursor.execute(sql)
        db_conn.commit()
        cfuncs.write_to_log(lg, "   TEMP_APP_SETTINGS table created OK")
    except:
        db_conn.rollback()
        cfuncs.write_to_log(lg, "   TEMP_APP_SETTINGS table creation failed!!")
        return None

    return 0


def check_for_settings_for_defaults_and_updates(db_conn, db_cursor):
    cfuncs.write_to_log(lg, ">> check_for_settings_for_defaults_and_updates()")
    
    settings = [('sensor_polling_freq', '600'),
                ('write_to_logfile', 'true'),
                ('start_up_status_email', 'false'),
                ('first_read_settle_time', '15'),
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
                cfuncs.write_to_log(lg, "   ADDED: Setting:  " + setting + "   Value: " + value)
                settings_added += 1
            except:
                db_conn.rollback()
                cfuncs.write_to_log(lg, "   TEMP_APP_SETTINGS table update failed!!")
                return None, None
        else:
            settings_existing += 1
            #cfuncs.write_to_log(lg, "   EXISTS: Setting:  " + setting + "   Value: " + value)
            
    cfuncs.write_to_log(lg, "<< check_for_settings_for_defaults_and_updates()")    
    return settings_existing, settings_added

    
def settings_db_to_dictionary(db_cursor):
    cfuncs.write_to_log(lg, ">> settings_db_to_dictionary")
    cfuncs.write_to_log(lg, "     Fetching settings from DB --> Dictionary")
    dictionary = {}
    
    query = "SELECT name, value FROM TEMP_APP_SETTINGS"
    db_cursor.execute(query)
    
    for row in db_cursor.fetchall():
        cfuncs.write_to_log(lg, "       Setting: " + str(row[0]) + " = " + str(row[1]))
        dictionary[str(row[0])] = str(row[1])
    cfuncs.write_to_log(lg, "<< settings_db_to_dictionary")
    return dictionary


def write_temp_reading_to_db(db_conn, db_cursor, db_sensor_id, temp_reading):
    cfuncs.write_to_log(lg, ">> write_temp_reading_to_db()")
    temp_reading = round(temp_reading, 1) 
    sql = "INSERT INTO TEMP_READINGS (date_added, temp_sensor_db_id, temperature) VALUES (NOW(), '" + str(db_sensor_id) + "', " + str(temp_reading) + ")"

    try:
        db_cursor.execute(sql)
        #print(db_cursor.execute(sql))
        db_conn.commit()
        cfuncs.write_to_log(lg, "   Temp including offset - " + str(temp_reading) + " added OK")
    except:
        db_conn.rollback()
        cfuncs.write_to_log(lg, "   Temp reading add failed!!")
    cfuncs.write_to_log(lg, "<< write_temp_reading_to_db()")


def reset_sensor_connected_status(db_conn, db_cursor):
    cfuncs.write_to_log(lg, ">> reset_sensor_connected_status()")
    try:
        update_sql = "UPDATE temps.TEMP_SENSORS SET connected = 0 WHERE sensor_id > 0"
        db_cursor.execute(update_sql)
        db_conn.commit()
        cfuncs.write_to_log(lg, "   reset sensor connected status for all OK")
    except:
        db_conn.rollback()
        cfuncs.write_to_log(lg, "   reset sensor connected status update failed!!")
        # do something else here!?!?!?!
        return None;
    return 0;
    cfuncs.write_to_log(lg, "<< reset_sensor_connected_status()")
    return id, temp_offset


def read_last_change_file_and_remove():
    reason = None
    change_file_path = "/home/steve/temperature_monitoring/last_change.txt"
    change_file = Path(change_file_path)
    if change_file.is_file():   
        #print("file exists")
        change_file =  open("/home/steve/temperature_monitoring/last_change.txt", 'r')
        reason = change_file.read()
        print(reason)
        change_file.close()
        os.system("rm -f " + change_file_path)
            
    return reason


def dump_all_db_data_out(db_cursor):
    query = "SELECT * FROM temps.TEMP_READINGS"
    db_cursor.execute(query)
    cfuncs.write_to_log(lg, "Current database contents for TEMP_READINGS......")
    for row in db_cursor.fetchall():
        id = str(row[0])
        date = str(row[1])
        temp_sensor_db_id = str(row[2])
        temp_sensor_id = str(row[2])
        temp = str(row[4])
        write_to_log(id + " " + date + " " + temp_sensor_db_id + " " + temp_sensor_id + " " + temp)


def send_email(user, pwd, recipient, subject, body):
    cfuncs.write_to_log(lg, ">> send_email()")
    FROM = user
    TO = recipient if isinstance(recipient, list) else [recipient]
    SUBJECT = subject
    TEXT = body

    # Prepare actual message
    message = "From: %s\nTo: %s\nSubject: %s\n\n%s" % (FROM, ", ".join(TO), SUBJECT, TEXT)
    
    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        status = server.ehlo()
        cfuncs.write_to_log(lg, "       ehlo:  " + str(status))
        status = server.starttls()
        cfuncs.write_to_log(lg, "   starttls:  " + str(status))
        status = server.login(user, pwd)
        cfuncs.write_to_log(lg, " user login:  " + str(status))
        server.sendmail(FROM, TO, message)
        server.close()
        cfuncs.write_to_log(lg, " email sent OK")
    except:
        cfuncs.write_to_log(lg, "****** failed to send email!!")

    cfuncs.write_to_log(lg, "<< send_email()")

#############################################################################################################

def do_main():
    global Global_db_conn
    global Global_db_cursor
    global Global_dict
    global send_start_up_status_email
    
    setup_gpio()
    os.system('clear')
    last_change_string = read_last_change_file_and_remove()
    clean_old_log_file()
    cfuncs.write_to_log(lg, "\n\n************  Started  -  all_temps_to_DB.py  ************\n")

    safe_to_unplug(True)
    all_sensors_list = None
    cfuncs.write_to_log(lg, "------------------------    Checking Network Connection is OK   ------------------------")

    ssid, quality, level = cfuncs.check_wireless_network_connection(lg)
    if ssid != '':
        network_status(True)
    else:
        network_status(False)

    ip_address = cfuncs.get_local_ip_address(lg)
    cfuncs.write_to_log(lg, "------------------------    Database Connection OK   -----------------------")

    db_conn = cfuncs.setup_db_connection(lg, "localhost", database_name, database_user_name, database_password)
    if db_conn is None:
        cfuncs.write_to_log(lg, "ERROR  - DB connection failed!")
        clean_shutdown()
    else:
        cfuncs.write_to_log(lg, "   DB connection OK")

    cursor = db_conn.cursor()
    Global_db_conn = db_conn
    Global_db_cursor = cursor

    #Setup a Query
    #query = "SELECT * FROM test.temps WHERE date_of_reading < STR_TO_DATE('24/12/2018 17:00', '%d/%m/%Y %H:%i') "
    safe_to_unplug(False)
    
    manage_settings_db_and_dict_stuff(db_conn, cursor)

    result = cfuncs.check_table_exists(lg, cursor, "TEMP_READINGS")
    if result is None:
        cfuncs.write_to_log(lg, "*** NO TEMP_READINGS Table")
        if create_temp_readings_table(cursor) is None:
            clean_shutdown()
    else:
        cfuncs.write_to_log(lg, "   OK - TEMP_READINGS table exists")

    result = cfuncs.check_table_exists(lg, cursor, "TEMP_SENSORS")
    if result is None:
        cfuncs.write_to_log(lg, "*** NO TEMP_SENSORS Table")
        if create_sensors_table(db_conn, cursor) is None:
            clean_shutdown()
    else:
        cfuncs.write_to_log(lg, "   OK - TEMP_SENSORS table exists")

    cfuncs.write_to_log(lg, "-------------------    Finished DB connection and setup all OK   -------------------")

    safe_to_unplug(True)
    result = reset_sensor_connected_status(db_conn, cursor)
    if result is None:
        cfuncs.write_to_log(lg, "ERROR - sensor connection status reset failed!")
        if create_sensors_table(db_conn, cursor) is None:
            clean_shutdown()

    while all_sensors_list is None:
        all_sensors_list = cfuncs.find_all_temp_sensors_connected(lg)
        if all_sensors_list is None:
            cfuncs.write_to_log(lg, "***Waiting 5 seconds before trying again")
            time.sleep(5)

    no_of_sensors = len(all_sensors_list)
    if no_of_sensors == 3:
        expected_sensor_count(True)
    else:
        expected_sensor_count(False)

    send_start_up_status_email = Global_dict['start_up_status_email']
    #Override for start emails!
    send_start_up_status_email = "true"
    
    if email_user is not None and email_passwd is not None and email_recipient_addr is not None:
        if send_start_up_status_email == "true":
            if last_change_string is None:
                last_change_string = "User restart or other unplanned restart"
            send_email(email_user, email_passwd, email_recipient_addr,  
                   "PI Temperature Monitoring Reset/Power Up Alert", 
                   "Reset reason:   " + last_change_string + "\n\n" + 
                   "\nConnected WiFi network: " + ssid + "  -  OK\n\nInitial startup and checking of DB  -  OK\n\n" + 
                   "Temperature Sensors detected:  "+ str(len(all_sensors_list)) + 
                   "\n\n\nHome page:  http://" + ip_address + "/home\n")
    else:
        cfuncs.write_to_log(lg, "***************************  Email credentials not all present, check env variable in /etc/environment!")
        cfuncs.write_to_log(lg, "Email user: " + str(email_user))
        cfuncs.write_to_log(lg, "Email passwd: " + str(email_passwd))
        cfuncs.write_to_log(lg, "Email recipient: " + str(email_recipient_addr))
    
    settle_time = int(Global_dict['first_read_settle_time'])
    cfuncs.write_to_log(lg, "Waiting %d seconds for the initial readings" % settle_time)
    time.sleep(settle_time)

    while True:            
        all_sensors_list = cfuncs.find_all_temp_sensors_connected(lg)
        no_of_sensors = len(all_sensors_list)
        if no_of_sensors == 3:
            expected_sensor_count(True)
        else:
            expected_sensor_count(False)
                   
        for sensor_name in all_sensors_list:
            db_sensor_id, alias, offset = cfuncs.find_temp_sensor_id_alias_and_offset(lg, db_conn, cursor, sensor_name, True)      
            cfuncs.write_to_log(lg, "   DB Sensor ID: " + str(db_sensor_id) + "   Temp Offset: " + str(offset))
            safe_to_unplug(False)
            if db_sensor_id is not None:
                temperature = cfuncs.read_temp(lg, sensor_name)
                if temperature is not None:
                    write_temp_reading_to_db(db_conn, cursor, db_sensor_id, (temperature + offset))
                else:
                    cfuncs.write_to_log(lg, "***Unable to obtain temperature reading! Return from call was None")
            else:
                cfuncs.write_to_log(lg, "***No info for sensor " + sensor_name + ", ignoring! Temp is " + str(read_temp(sensor_name)))
        loop_time = int(Global_dict['sensor_polling_freq'])
        cfuncs.write_to_log(lg, "The next reading will be taken in " + str(int(round(loop_time / 60, 0))) + " minutes")
        safe_to_unplug(True)
        
        net_checking_count = 10
        net_checking_loop_time = (loop_time / net_checking_count)
        for count in range(0,net_checking_count-1):
            cfuncs.write_to_log(lg, "In network monitor loop(" + str(count) + ") before resampling temps again")
            ssid, quality, level = cfuncs.check_wireless_network_connection(lg)
            if ssid != '':
                network_status(True)
            else:
                network_status(False)
            time.sleep(net_checking_loop_time)
            
        cfuncs.write_to_log(lg, "Exited network monitor loop, one for sleep before resampling temps again")    
        time.sleep(net_checking_loop_time)

########################################################################################################

#Setup Handler for catching ctrl+c and kill signal, then shutdown cleanly
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

do_main()
