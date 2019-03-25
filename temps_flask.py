#! /usr/bin/python3.5

import common_functions as cfuncs
import datetime
import MySQLdb
import glob
from flask import Flask, render_template, redirect, url_for, request, flash, send_from_directory
from wtforms import Form, IntegerField, BooleanField, TextField, TextAreaField, validators, StringField, SubmitField
import os
import socket
import subprocess
import time

lg = "web"
base_dir = '/sys/bus/w1/devices/'

app = Flask(__name__)
app.config.from_object(__name__)
app.config['SECRET_KEY'] = '7d441f27d441f27567d441f2b9176a'

#Example of charting: https://www.patricksoftwareblog.com/creating-charts-with-chart-js-in-a-flask-application/
#
#For Chart.js source goto link:
#https://github.com/chartjs/Chart.js/releases/latest

class SensorDisplayNameForm(Form):
    new_name1 = TextField('Display Name:', validators=[validators.optional(), validators.Length(min=1, max=20)])
    new_name2 = TextField('Display Name:', validators=[validators.optional(), validators.Length(min=1, max=20)])
    new_name3 = TextField('Display Name:', validators=[validators.optional(), validators.Length(min=1, max=20)])


@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')


@app.route("/updatesensornames", methods=['GET', 'POST'])
def SensorDisplayNameUpdate():
    form = SensorDisplayNameForm(request.form)
    
    #print(form.errors)
    if request.method == 'POST':
        new_name1 = request.form['new_name1'].strip()
        new_name2 = request.form['new_name2'].strip()
        new_name3 = request.form['new_name3'].strip()

        if new_name1 != "" or new_name2 != "" or new_name3 != "":
            if form.validate():
                cfuncs.write_to_log(lg, "   Form validated OK")
                all_sensors_uid_list = cfuncs.find_all_temp_sensors_connected(lg)
                newnames=[new_name1,new_name2,new_name3]
                #print(newnames)
                #print(all_sensors_uid_list)
                all_sensor_name_info = list(zip(all_sensors_uid_list, newnames))
                #print(all_sensor_name_info)
                for sensor_uid, new_name in all_sensor_name_info:
                    print("looking at: " + sensor_uid + " new_name: " + new_name)
                    if new_name != "":
                        #print("sensor_uid + "  " new_name  -  updating name in DB!")
                        cfuncs.update_sensor_display_name(lg, sensor_uid, new_name)
                return redirect(url_for('home'))
            else:
                print("Form NOT validated OK")

        return redirect(url_for('SensorDisplayNameUpdate'))
    else:
        all_sensors_list = cfuncs.find_all_temp_sensors_connected(lg)
        if all_sensors_list is not None:
            no_sensors = str(len(all_sensors_list))
            db_conn = cfuncs.setup_db_connection(lg, "localhost", "temps", "temps_user", "user")
            if db_conn is None:
                cfuncs.write_to_log(lg, "ERROR  - DB connection failed!")
                clean_shutdown()
            else:
                cfuncs.write_to_log(lg, "   DB connection OK")

            cursor = db_conn.cursor()
            sensor_aliases = []
            for sensor_id in all_sensors_list:
                db_id, temp_sensor_alias, temp_offset = cfuncs.find_temp_sensor_id_alias_and_offset(lg, db_conn, cursor, sensor_id, False)
                sensor_aliases.append(temp_sensor_alias)
            cursor.close()
            db_conn.close()

        all_sensor_info = list(zip(all_sensors_list, sensor_aliases))
        vstring = cfuncs.app_version()
        
        return render_template('sensor_display_name_update.html', 
                                form=form, 
                                version = vstring, 
                                sensors_ids=all_sensors_list, 
                                sensor_aliases=sensor_aliases)


@app.route("/")
@app.route("/home")
def home():
    vstring = cfuncs.app_version()
    all_sensors_list = cfuncs.find_all_temp_sensors_connected(lg)
    if all_sensors_list is not None:
    #                                         Log     Location   DB Name    DB Username   DB Passwd 
        db_conn = cfuncs.setup_db_connection("web", "localhost", "temps", "temps_reader", "reader")

        if db_conn is None:
            return("<html><h1>DB connection failed!</h1></html>")

        cursor = db_conn.cursor()
        
        sensors_connected = cfuncs.get_all_connected_sensor_ids("web", cursor)

        reading_dates = []
        temperatures = []
        temp_sensor_aliass = []
        temp_sensor_ids = []
        
        for sensor_id in sensors_connected:
            reading_date, temperature, temp_sensor_alias, temp_sensor_id = cfuncs.get_last_temperature_reading_from_db("web", cursor, sensor_id)
            reading_dates.append(reading_date)
            temperatures.append(temperature)
            temp_sensor_aliass.append(temp_sensor_alias)
            temp_sensor_ids.append(temp_sensor_id)
        
        temp_details = list(zip(temp_sensor_aliass, temp_sensor_ids, reading_dates, temperatures))
    else:
        temp_details = None
        
    return render_template('home.html', version = vstring,
                                        page_heading = 'Last Saved Temperature Readings', 
                                        title = 'Last Recorded',
                                        autorefresh_required = None,
                                        temp_data = temp_details)     


@app.route("/home2")
def home2():
    vstring = cfuncs.app_version()
    all_sensors_list = cfuncs.find_all_temp_sensors_connected(lg)
    if all_sensors_list is not None:
    #                                         Log     Location   DB Name    DB Username   DB Passwd 
        db_conn = cfuncs.setup_db_connection("web", "localhost", "temps", "temps_reader", "reader")

        if db_conn is None:
            return("<html><h1>DB connection failed!</h1></html>")

        cursor = db_conn.cursor()
        
        sensors_connected = cfuncs.get_all_connected_sensor_ids("web", cursor)
        
        reading_dates = []
        temperatures = []
        temp_sensor_aliass = []
        temp_sensor_ids = []
        
        for sensor_id in sensors_connected:
            reading_date, temperature, temp_sensor_alias, temp_sensor_id = cfuncs.get_last_temperature_reading_from_db("web", cursor, sensor_id)
            reading_dates.append(reading_date)
            temperatures.append(temperature)
            temp_sensor_aliass.append(temp_sensor_alias)
            temp_sensor_ids.append(temp_sensor_id)
        
        temp_details = list(zip(temp_sensor_aliass, temp_sensor_ids, reading_dates, temperatures))
    else:
        temp_details = None
        
    return render_template('home2.html', version = vstring,
                                        page_heading = 'Last Saved Temperature Readings', 
                                        title = 'Last Recorded', 
                                        temp_data = temp_details)     

@app.route("/check_for_updates")
def check_for_updates():
    result = cfuncs.check_for_updates(lg)
    if result is None:
        return redirect(url_for('status'))
    else:
        return redirect(url_for('update_done'))


@app.route("/update_done")
def update_done():
    cfuncs.write_to_last_change_file(lg, "Restart after user requested a software update")
    os.system("/sbin/shutdown -r 0")
    return ("<html><h2>Software updated!</h2></br><h2>The system will now restart......</h2></br></br><h3><a href=" + 
    url_for('home') + ">Reload the home page.....</a></h3></html>")
    
    
@app.route("/clear_log_archive")
def clear_log_archive():
    cfuncs.clear_log_archive(lg)
    return redirect(url_for('status'))


@app.route("/clear_app_settings")
def clear_app_settings():
    result = cfuncs.reset_db_table(lg, "TEMP_APP_SETTINGS")
    if result is False:
        return redirect(url_for('status'))
    else:
        return redirect(url_for('cleared_app_settings'))


@app.route("/cleared_app_settings")
def cleared_app_settings():
    cfuncs.write_to_last_change_file(lg, "Restart after user requested all settings reset to default")
    os.system("/sbin/shutdown -r 0")
    return ("<html><h2>Settings reset to defaults</h2></br><h2>The system will now restart......</h2></br></br><h3><a href=" + 
    url_for('home') + ">Reload the home page.....</a></h3></html>")


@app.route("/clear_temp_readings")
def clear_temp_readings():
    result = cfuncs.reset_db_table(lg, "TEMP_READINGS")
    if result is False:
        return redirect(url_for('utils'))
    else:
        return redirect(url_for('home'))


@app.route("/current_temps")
def current_temps():
    vstring = cfuncs.app_version()
    all_sensors_list = cfuncs.find_all_temp_sensors_connected(lg)
    if all_sensors_list is not None:
        no_sensors = str(len(all_sensors_list))
    #                                         Log     Location   DB Name    DB Username   DB Passwd 
        db_conn = cfuncs.setup_db_connection("web", "localhost", "temps", "temps_reader", "reader")

        if db_conn is None:
            return("<html><h1>DB connection failed!</h1></html>")

        cursor = db_conn.cursor()
         
        sensor_names = []
        sensor_ids = []
        temp_readings = []
        current_datetime = []
        for sensor_name in all_sensors_list:
            db_sensor_id, alias, offset = cfuncs.find_temp_sensor_id_alias_and_offset(lg, db_conn, cursor, sensor_name, False)      
            if db_sensor_id is not None:
                temperature = cfuncs.read_temp(lg, sensor_name) + offset
                temperature = round(temperature,1)                          # Round to 1 decimal place
                sensor_names.append(alias)
                sensor_ids.append(sensor_name)
                temp_readings.append(str(temperature))
                
                now = datetime.datetime.now()
                current_datetime.append(now.strftime("%d/%m/%y %X"))     # 24-Hour:Minute

        temp_details = list(zip(sensor_names, sensor_ids, current_datetime, temp_readings))
    else:
        temp_details = None
        
    return render_template('live_temps.html', version = vstring,
                                        page_heading = 'Current Temperature Readings', 
                                        title = 'Current Temps',
                                        autorefresh_required = True,
                                        temp_data = temp_details)


@app.route("/restart_now")
def restart_now():
    cfuncs.write_to_last_change_file(lg, "User requested restart")
    os.system("/sbin/shutdown -r 0")
    return ("<h2>The system will now restart......</h2></br></br><h3><a href=" + 
    url_for('home') + ">Reload the home page.....</a></h3></html>") 


@app.route("/shutdown")
def shutdown():
    cfuncs.write_to_last_change_file(lg, "User requested shutdown")
    os.system("/sbin/shutdown 0")
    return ("<h2>The system will now shutdown......</h2></html>") 


@app.route("/status")
def status():
    sensor_aliases = None
    no_sensors = 0
    public_ip = None
    record_count = 0
    
    ssid, quality, level = cfuncs.check_wireless_network_connection(lg)
    if (level <= -100):
        level_perc = 0
    elif (level >= -50):
        level_perc = 100
    else:
        level_perc = 2 * (level + 100)
        
    quality_perc = 2 * (quality + 100)
    all_sensors_list = cfuncs.find_all_temp_sensors_connected(lg)
    if all_sensors_list is not None:
        no_sensors = str(len(all_sensors_list))
        db_conn = cfuncs.setup_db_connection(lg, "localhost", "temps", "temps_user", "user")
        if db_conn is None:
            cfuncs.write_to_log(lg, "ERROR  - DB connection failed!")
            clean_shutdown()
        else:
            cfuncs.write_to_log(lg, "   DB connection OK")

        cursor = db_conn.cursor()
        sensor_aliases = []
        for sensor_id in all_sensors_list:
            db_id, temp_sensor_alias, temp_offset = cfuncs.find_temp_sensor_id_alias_and_offset(lg, db_conn, cursor, sensor_id, False)
            sensor_aliases.append(temp_sensor_alias)
            
        record_count = cfuncs.get_total_temp_reading_records_count_from_db(lg, cursor)
            
        cursor.close()
        db_conn.close()
        all_sensor_info = list(zip(all_sensors_list, sensor_aliases))
    else:
        all_sensor_info = None
    
    now = datetime.datetime.now()
    date_and_time = str(now.day) + "/"+ str(now.month).zfill(2) + "/" + str(now.year) + " " + str(now.hour).zfill(2) + ":" + str(now.minute).zfill(2) + ":" + str(now.second).zfill(2)
    ip_address = cfuncs.get_local_ip_address("web")
    public_ip = cfuncs.get_public_ip(lg)
    vstring = cfuncs.app_version()
    os, architecture, oskernel, firmwareversion, uptime = cfuncs.get_system_information()
    cputemp = cfuncs.get_cpu_temp(lg)
    total_capacity, free_space, disk_used = cfuncs.get_filesystem_stats(lg)
    logs_directory_size = cfuncs.get_size_of_directory(lg, '/home/steve/temperature_monitoring/logs')
    log_file_size = cfuncs.get_size_of_file(lg, '/home/steve/temperature_monitoring/log.txt')

    return render_template('status.html',
                            version=vstring,
                            page_heading='System Information',
                            title='Sys Info',
                            os = os, 
                            architecture = architecture,
                            oskernel = oskernel,
                            uptime = uptime,
                            cputemp = cputemp,
                            firmwareversion = firmwareversion,
                            hostname = socket.gethostname(),
                            disk_capacity = total_capacity,
                            disk_used = disk_used,
                            disk_free_space = free_space,
                            logs_size = logs_directory_size,
                            log_file = log_file_size,
                            total_records = record_count,
                            ip = ip_address,
                            publicip = public_ip,
                            ssid=ssid,
                            quality=str(quality),
                            level_perc=str(level_perc),
                            level=str(level),
                            no_sensors=no_sensors,
                            sensors_list=all_sensor_info)


class SettingsUpdateForm(Form):
    new_value0 = IntegerField('Temp Sensor Reading Frequency (mins)', validators=[validators.optional(), validators.NumberRange(min=1, max=60)])
    new_value1 = BooleanField('Logfile Enabled (not implemented yet)', validators=[validators.optional()])
    new_value2 = TextField('Power Up Email Recipient', validators=[validators.optional(), validators.Email()])
    new_value3 = BooleanField('Send Start Up Email', validators=[validators.optional()])
    new_value4 = IntegerField('Web Page Auto-Refresh Time (mins)', validators=[validators.optional(), validators.NumberRange(min=1, max=60)])
    new_value5 = IntegerField('First Temp Read Settle Time (s)', validators=[validators.optional(), validators.NumberRange(min=1, max=30)])
    new_value6 = IntegerField('Max Time To Keep Temp Readings (months)', validators=[validators.optional(), validators.NumberRange(min=1, max=12)])
    new_value7 = IntegerField('Line Thickness for Charts', validators=[validators.optional(), validators.NumberRange(min=1, max=10)])
    new_value8 = IntegerField('Time Period for "User" Chart (hours)', validators=[validators.optional(), validators.NumberRange(min=1, max=672)])

@app.route("/utils", methods=['GET', 'POST'])
def utils():
    form = SettingsUpdateForm(request.form)
    setting_name = []
    setting_value = []

    #print(form.errors)
    
    db_conn = cfuncs.setup_db_connection(lg, "localhost", "temps", "temps_user", "user")
    if db_conn is None:
        cfuncs.write_to_log(lg, "ERROR  - DB connection failed!")
        clean_shutdown()
    else:
        cfuncs.write_to_log(lg, "   DB connection OK")

    cursor = db_conn.cursor()
    
    settings_dict = cfuncs.settings_db_to_dictionary(lg, cursor)

    setting_name.append('sensor_polling_freq')
    setting_name.append('write_to_logfile')
    setting_name.append('start_up_email_address')
    setting_name.append('start_up_status_email')
    setting_name.append('webpage_autorefresh_time')
    setting_name.append('first_read_settle_time')
    setting_name.append('temp_reading_max_age')
    setting_name.append('line_chart_line_thickness')
    setting_name.append('user_period_line_chart')

    setting_value.append(settings_dict['sensor_polling_freq'])
    setting_value.append(settings_dict['write_to_logfile'])
    if settings_dict['start_up_email_address'] == 'not_set':
        setting_value.append("Internal Default")
    else:
        setting_value.append(settings_dict['start_up_email_address'])
    setting_value.append(settings_dict['start_up_status_email'])
    setting_value.append(settings_dict['webpage_autorefresh_time'])
    setting_value.append(settings_dict['first_read_settle_time'])
    setting_value.append(settings_dict['temp_reading_max_age'])
    setting_value.append(settings_dict['line_chart_line_thickness'])
    setting_value.append(settings_dict['user_period_line_chart'])
    
    cursor.close()
    db_conn.close()
    
    if request.method == 'POST':
        sensor_polling_freq = request.form['new_value0']
        write_to_logfile = str(form.new_value1.data)
        start_up_email_address = str(form.new_value2.data).strip()
        start_up_status_email = str(form.new_value3.data)
        webpage_autorefresh_time = request.form['new_value4'].strip()
        first_read_settle_time = request.form['new_value5']
        temp_reading_max_age = request.form['new_value6']
        line_chart_line_thickness = request.form['new_value7']
        user_period_line_chart = request.form['new_value8']
       
        if form.validate():
            cfuncs.write_to_log(lg, "   Form validated OK")
            if sensor_polling_freq != '':
               cfuncs.update_setting(lg, 'sensor_polling_freq', sensor_polling_freq)
                   
            if write_to_logfile != settings_dict['write_to_logfile']:
                cfuncs.update_setting(lg, 'write_to_logfile', write_to_logfile)

            if start_up_email_address != '':
                cfuncs.update_setting(lg, 'start_up_email_address', start_up_email_address)
            
            if start_up_status_email != settings_dict['start_up_status_email']:
                cfuncs.update_setting(lg, 'start_up_status_email', start_up_status_email)

            if webpage_autorefresh_time != '':
                cfuncs.update_setting(lg, 'webpage_autorefresh_time', webpage_autorefresh_time)
                
            if first_read_settle_time != '':
                cfuncs.update_setting(lg, 'first_read_settle_time', first_read_settle_time)

            if temp_reading_max_age != '':
                cfuncs.update_setting(lg, 'temp_reading_max_age', temp_reading_max_age)
                
            if line_chart_line_thickness != '':
                cfuncs.update_setting(lg, 'line_chart_line_thickness', line_chart_line_thickness)

            if user_period_line_chart != '':
                cfuncs.update_setting(lg, 'user_period_line_chart', user_period_line_chart)

        else:
            print("Form NOT validated OK")
        
        return redirect(url_for('utils'))
    else:

        if setting_value[1] == "True":
            temp1 = True
        else:
            temp1 = False
            
        if setting_value[3] == "True":
            temp3 = True
        else:
            temp3 = False
            
        vstring = cfuncs.app_version()
            
        return render_template('utils.html', 
                                form=form,
                                page_heading = 'System Utils',
                                version = vstring,
                                title = "Utils", 
                                setting_name = setting_name, 
                                setting_value = setting_value,
                                tmp1 = temp1, tmp3 = temp3)


@app.route("/timeline_chart")
def timeline_chart():
    #                                             Location   DB Name    DB Username   DB Passwd 
    db_conn = cfuncs.setup_db_connection(lg, "localhost", "temps", "temps_reader", "reader")

    #db_conn = cfuncs.setup_db_connection(lg, "localhost", "temps", "temps_user", "user")
    if db_conn is None:
        return("<html><h1>ERROR  - DB connection failed!</h1></html>")

    cursor = db_conn.cursor()
    
    settings_dict = cfuncs.settings_db_to_dictionary(lg, cursor)
    web_refresh_time = settings_dict['webpage_autorefresh_time']
    line_thickness = settings_dict['line_chart_line_thickness']
    
    requested_period_hours = request.args.get('hours', None)
    if requested_period_hours == 'User':
        requested_period_hours = settings_dict['user_period_line_chart']
    if int(requested_period_hours) < 1:
        return("<html><h1>Invalid number of hours requested!</h1></html>")
        
    db_temp_readings_table = "TEMP_READINGS"
    result = cfuncs.check_table_exists(lg, cursor, db_temp_readings_table)

    if result is None:
        cursor.close()
        db_conn.close()
        return("<html><h1>TEMP_READINGS DB table does not exist!</h1></html>")

    no_of_sensors, sensor_list = get_no_of_sensors_and_sensor_id_in_db(cursor)
    if no_of_sensors == 0:
        return("<html><h1>No temperature data for today yet!</h1></html>")

    if no_of_sensors != 3:
        return("<html><h1>Data for %d sensors found</h1><h1>Charting only works for 3 sensors currently!</h1></html>" % no_of_sensors)
    
    query = """SELECT CONCAT(YEAR(TEMP_READINGS.date_added),',',
                             MONTH(TEMP_READINGS.date_added),',',
                             DAY(TEMP_READINGS.date_added),',',
                             HOUR(TEMP_READINGS.date_added),',',
                             MINUTE(TEMP_READINGS.date_added)) as time_added, 
                      temperature, 
                      temp_sensor_db_id, 
                      temp_sensor_alias 
               FROM temps.TEMP_READINGS 
               JOIN TEMP_SENSORS ON temp_sensor_db_id = TEMP_SENSORS.sensor_id
               WHERE TEMP_READINGS.date_added >= (now() - INTERVAL """ + requested_period_hours + """ HOUR)
               ORDER BY TEMP_READINGS.date_added ASC"""

    cursor.execute(query)

    date = []
    temps = []
    data1 = []
    data2 = []
    data3 = []

    for row in cursor.fetchall():  #row[0]:date, row[1]:temp, row[2]:sensor_id, row[3]:sensor_name
        if row[2] == sensor_list[0]:
            legend1 = str(row[3])
            data1.append("{x: new Date(" + row[0] + "), y: " + str(row[1]) +"}")
        if row[2] == sensor_list[1]:
            legend2 = str(row[3])
            data2.append("{x: new Date(" + row[0] + "), y: " + str(row[1]) +"}")
        if row[2] == sensor_list[2]:
            legend3 = str(row[3])
            data3.append("{x: new Date(" + row[0] + "), y: " + str(row[1]) +"}")
    
    cursor.close()
    db_conn.close()
    vstring = cfuncs.app_version()
    
    xhoursbefore = datetime.datetime.now() - datetime.timedelta(hours=int(requested_period_hours))
    now = datetime.datetime.now()
    xaxis_info = []
    xaxis_info.append("new Date(" + str(xhoursbefore.year) + "," + str(xhoursbefore.month) + "," + str(xhoursbefore.day) + "," + str(xhoursbefore.hour) + "," + str(xhoursbefore.minute) + ")")
    xaxis_info.append("new Date(" + str(now.year) + "," + str(now.month) + "," + str(now.day) + "," + str(now.hour) + "," + str(now.minute) + ")")
    
    date_only = False
    
    if int(requested_period_hours) > 48:
        date_only = True
        
    if int(requested_period_hours) == 1 * 24:
        chart_title = 'Temperature Readings for the previous Day'
        page_title = '1 Day Temps'
    elif int(requested_period_hours) == 2 * 24:
        chart_title = 'Temperature Readings for the previous 2 Days'
        page_title = '2 Days Temps'
    elif int(requested_period_hours) == 3 * 24:
        chart_title = 'Temperature Readings for the previous 3 Days'
        page_title = '3 Days Temps'
    elif int(requested_period_hours) == 4 * 24:
        chart_title = 'Temperature Readings for the previous 4 Days'
        page_title = '4 Days Temps'
    elif int(requested_period_hours) == 5 * 24:
        chart_title = 'Temperature Readings for the previous 5 Days'
        page_title = '5 Days Temps'
    elif int(requested_period_hours) == 6 * 24:
        chart_title = 'Temperature Readings for the previous 6 Days'
        page_title = '6 Days Temps'
    elif int(requested_period_hours) == 7 * 24:
        chart_title = 'Temperature Readings for the previous Week'
        page_title = '1 Week Temps'
    elif int(requested_period_hours) > 1:
        chart_title = 'Temperature Readings for the previous ' + requested_period_hours + ' hours'
        page_title = requested_period_hours + 'hrs Temps'
    else:
        chart_title = 'Temperature Readings for the previous ' + requested_period_hours + ' hour'
        page_title = requested_period_hours + 'hr Temps'
        
    return render_template('time_line_chart.html',
                           version = vstring,
                           page_heading = '',
                           title = page_title,
                           autorefresh_required = True,
                           refresh_time = web_refresh_time,
                           temps1 = str(data1).replace('\'', ''), 
                           temps2 = str(data2).replace('\'', ''), 
                           temps3 = str(data3).replace('\'', ''), 
                           series1 = legend1, 
                           series2 = legend2, 
                           series3 = legend3,
                           chart_title = chart_title,
                           xaxis = xaxis_info,
                           date_only = date_only,
                           line_thickness = line_thickness)


@app.route("/today_chart")
def today_chart():
    #                                             Location   DB Name    DB Username   DB Passwd 
    db_conn = cfuncs.setup_db_connection(lg, "localhost", "temps", "temps_reader", "reader")

    #db_conn = cfuncs.setup_db_connection(lg, "localhost", "temps", "temps_user", "user")
    if db_conn is None:
        return("<html><h1>ERROR  - DB connection failed!</h1></html>")

    cursor = db_conn.cursor()
    
    settings_dict = cfuncs.settings_db_to_dictionary(lg, cursor)
    web_refresh_time = settings_dict['webpage_autorefresh_time']
    line_thickness = settings_dict['line_chart_line_thickness']
    
    db_temp_readings_table = "TEMP_READINGS"
    result = cfuncs.check_table_exists(lg, cursor, db_temp_readings_table)

    if result is None:
        cursor.close()
        db_conn.close()
        return("<html><h1>TEMP_READINGS DB table does not exist!</h1></html>")

    no_of_sensors, sensor_list = get_no_of_sensors_and_sensor_id_in_db(cursor)
    if no_of_sensors == 0:
        return("<html><h1>No temperature data for today yet!</h1></html>")

    if no_of_sensors != 3:
        return("<html><h1>Data for %d sensors found</h1><h1>Charting only works for 3 sensors currently!</h1></html>" % no_of_sensors)
    
    query = """SELECT CONCAT(YEAR(TEMP_READINGS.date_added),',',MONTH(TEMP_READINGS.date_added),',',DAY(TEMP_READINGS.date_added),',',HOUR(TEMP_READINGS.date_added),',',MINUTE(TEMP_READINGS.date_added)) as time_added, 
                      temperature, 
                      temp_sensor_db_id, 
                      temp_sensor_alias 
               FROM temps.TEMP_READINGS 
               JOIN TEMP_SENSORS ON temp_sensor_db_id = TEMP_SENSORS.sensor_id
               WHERE 
               DAYOFMONTH(TEMP_READINGS.date_added) = DAYOFMONTH(NOW())
               AND MONTH(TEMP_READINGS.date_added) = MONTH(NOW()) 
               AND YEAR(TEMP_READINGS.date_added) = YEAR(NOW())"""
    
    cursor.execute(query)

    date = []
    temps = []
    data1 = []
    data2 = []
    data3 = []

    for row in cursor.fetchall():  #row[0]:date, row[1]:temp, row[2]:sensor_id, row[3]:sensor_name
        if row[2] == sensor_list[0]:
            legend1 = str(row[3])
            data1.append("{x: new Date(" + row[0] + "), y: " + str(row[1]) +"}")
        if row[2] == sensor_list[1]:
            legend2 = str(row[3])
            data2.append("{x: new Date(" + row[0] + "), y: " + str(row[1]) +"}")
        if row[2] == sensor_list[2]:
            legend3 = str(row[3])
            data3.append("{x: new Date(" + row[0] + "), y: " + str(row[1]) +"}")
    
    #formatted_data = str(data1).replace('\'', '')
    #print(formatted_data)
    #print(data1)
    
    cursor.close()
    db_conn.close()
    vstring = cfuncs.app_version()
    
    now = datetime.datetime.now()
    xaxis_info = []
    # X Axis to start at 00:00 and end at 24:00 of the same day i.e. the current day!
    xaxis_info.append("new Date(" + str(now.year) + "," + str(now.month) + "," + str(now.day) + ",0,0)")
    xaxis_info.append("new Date(" + str(now.year) + "," + str(now.month) + "," + str(now.day) + ",23,59)")
    
    page_title = 'Todays Temps'
    chart_title = 'Temperature Readings for Today Only'
    return render_template('time_line_chart.html',
                           version=vstring,
                           page_heading = '',
                           title=page_title,
                           autorefresh_required = True,
                           refresh_time = web_refresh_time,
                           temps1=str(data1).replace('\'', ''), 
                           temps2=str(data2).replace('\'', ''), 
                           temps3=str(data3).replace('\'', ''), 
                           series1=legend1, 
                           series2=legend2, 
                           series3=legend3,
                           chart_title=chart_title,
                           xaxis = xaxis_info,
                           line_thickness = line_thickness)


@app.route("/weekoverview_chart")
def weekoverview_chart():
    #                                             Location   DB Name    DB Username   DB Passwd 
    db_conn = cfuncs.setup_db_connection("web", "localhost", "temps", "temps_reader", "reader")

    db_temp_readings_table = "TEMP_READINGS"
    if db_conn is None:
        return("<html><h1>DB connection failed!</h1></html>")

    cursor = db_conn.cursor()
    result = cfuncs.check_table_exists("web", cursor, db_temp_readings_table)

    if result is None:
        cursor.close()
        db_conn.close()
        return("<html><h1>TEMP_READINGS DB table does not exist!</h1></html>")

    no_of_sensors, sensor_list = get_no_of_sensors_and_sensor_id_in_db(cursor)

    if no_of_sensors == 0:
        return("<html><h1>No temperature data for today yet!</h1></html>")

    if no_of_sensors != 3:
        return("<html><h1>Data for %d sensors found</h1><h1>Charting only works for 3 sensors currently!</h1></html>" % no_of_sensors)
    
    all_sensor_aliases = []
    all_dates = []
    all_min_temps = []
    all_avg_temps = []
    all_max_temps = []
    
    for sensor in sensor_list:
        dates = []
        min_temps = []
        avg_temps = []
        max_temps = []
        query = """SELECT DATE_FORMAT(TEMP_READINGS.date_added, '%d/%m/%y'), 
                          MIN(TEMP_READINGS.temperature), 
                          ROUND(AVG(TEMP_READINGS.temperature), 1), 
                          MAX(TEMP_READINGS.temperature),
                          TEMP_SENSORS.temp_sensor_alias
                          FROM TEMP_READINGS
                          JOIN TEMP_SENSORS ON temp_sensor_db_id = TEMP_SENSORS.sensor_id
                          WHERE TEMP_READINGS.temp_sensor_db_id = """ + str(sensor) + """
                          GROUP BY DATE_FORMAT(TEMP_READINGS.date_added, '%d/%m/%y')
                          ORDER BY TEMP_READINGS.date_added DESC 
                          LIMIT 7"""
        cursor.execute(query)
        count = 0
        for row in cursor.fetchall():  #row[0]:date, row[1]:temp, row[2]:sensor_id, row[3]:sensor_name
            if count == 0:
                all_sensor_aliases.append(row[4])
                count += 1
            dates.append(str(row[0]))
            min_temps.append(row[1])
            avg_temps.append(row[2])
            max_temps.append(row[3])

        all_dates.append(list(reversed(dates)))
        all_min_temps.append(list(reversed(min_temps)))
        all_avg_temps.append(list(reversed(avg_temps)))
        all_max_temps.append(list(reversed(max_temps)))
    
    cursor.close()
    db_conn.close()
    vstring = cfuncs.app_version()
    page_title = 'Daily Stats'
    chart_title1 = 'Daily Overview of Temperatures (' + all_sensor_aliases[0] + ')'
    chart_title2 = 'Daily Overview of Temperatures (' + all_sensor_aliases[1] + ')'
    chart_title3 = 'Daily Overview of Temperatures (' + all_sensor_aliases[2] + ')'
    return render_template('weekoverview_chart.html',
                           version=vstring,
                           title=page_title,
                           chart_title1=chart_title1,
                           autorefresh_required = False,
                           date_labels1 = all_dates[0],
                           mins1 = all_min_temps[0],
                           avgs1 = all_avg_temps[0],
                           maxs1 = all_max_temps[0],
                           chart_title2=chart_title2,
                           date_labels2 = all_dates[1],
                           mins2 = all_min_temps[1],
                           avgs2 = all_avg_temps[1],
                           maxs2 = all_max_temps[1],
                           chart_title3=chart_title3,
                           date_labels3= all_dates[2],
                           mins3 = all_min_temps[2],
                           avgs3 = all_avg_temps[2],
                           maxs3 = all_max_temps[2])


def run_query_and_dump_all_db_data_out(db_cursor, query, description):
    db_cursor.execute(query)
    all_data = "<html>"
    all_data += "<h1>" + description + "</h1></br>"
    all_data += "<table style=""width:50%"">"

    all_data += "<tr align=""center"" bgcolor=""#8990f7""><th>DateTime</th><th>Sensor Alias</th><th>Temperature</th></tr>"
    for row in db_cursor.fetchall():
        #print(row)
        datetime = str(row[0])
        sensor_alias = str(row[1])
        temperature = str(row[2])

        all_data = all_data + "<tr align=""center"" bgcolor=""#f1efff"" bordercolor=""black"">"
        all_data = all_data + "<td>" + datetime + "</td>"
        all_data = all_data + "<td>" + sensor_alias + "</td>"
        all_data = all_data + "<td>" + temperature + "</td>"
        all_data = all_data + "</tr>"
    all_data += "</table>"
    all_data += "</h2></html>"
    return all_data


def run_query_and_dump_out_overview(db_cursor, query, description):
    #print("Running Query: " + query)
    db_cursor.execute(query)
    all_data = "<html>"
    all_data += "<h1> " + description + "</h1></br><h2>"
    #print("\n" + description)
    for row in db_cursor.fetchall():
        #print(row)
        date = str(row[0])
        min = str(row[1])
        avg = str(row[2])
        max = str(row[3])
        all_data = all_data + date + " " + min + " " + avg + " " + max + "</br>"
    all_data += "</h2></html>"
    return all_data


def get_no_of_sensors_and_sensor_id_in_db(db_cursor):
    
    query = """SELECT temp_sensor_db_id FROM temps.TEMP_READINGS 
           WHERE 
           DAYOFMONTH(TEMP_READINGS.date_added) = DAYOFMONTH(NOW())
           AND MONTH(TEMP_READINGS.date_added) = MONTH(NOW()) 
           AND YEAR(TEMP_READINGS.date_added) = YEAR(NOW())
           GROUP BY temp_sensor_db_id"""
               
    db_cursor.execute(query)
    no_of_sensors = db_cursor.rowcount

    sensor_ids = []
    for row in db_cursor.fetchall():
        sensor_ids.append(row[0])
    #print(sensor_ids)
    return no_of_sensors, sensor_ids


if __name__ == '__main__':
    cfuncs.clean_old_log_file()
    app.run(host='0.0.0.0', port=80, debug=True)
    
