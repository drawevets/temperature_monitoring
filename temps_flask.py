#! /usr/bin/python3.5

import common_functions as cfuncs
import datetime
import MySQLdb
import glob
from flask import Flask
from flask import render_template
import os
from pathlib import Path
import socket
import subprocess

lg = "web"
base_dir = '/sys/bus/w1/devices/'

app = Flask(__name__)

#Example of charting: https://www.patricksoftwareblog.com/creating-charts-with-chart-js-in-a-flask-application/
#
#For Chart.js source goto link:
#https://github.com/chartjs/Chart.js/releases/latest

@app.route("/")
@app.route("/home")
def home():
    vstring = cfuncs.app_version()
    all_sensors_list = cfuncs.find_all_temp_sensors_connected(lg)
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
    
    #print(temp_details)
    
    return render_template('home.html', version = vstring,
                                        page_heading = 'Last Recorded Temperature Readings', 
                                        title = 'Last Recorded', 
                                        temp_data = temp_details)     


@app.route("/")
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
                                        temp_data = temp_details)  


@app.route("/status")
def status():
    ssid, quality, level = cfuncs.check_wireless_network_connection(lg)
    
    all_sensors_list = cfuncs.find_all_temp_sensors_connected(lg)
    if all_sensors_list is not None:
        no_sensors = str(len(all_sensors_list))
    else:
        no_sensors = 0
        
    now = datetime.datetime.now()
    date_and_time = str(now.day) + "/"+ str(now.month).zfill(2) + "/" + str(now.year) + " " + str(now.hour).zfill(2) + ":" + str(now.minute).zfill(2) + ":" + str(now.second).zfill(2)
    ip_address = cfuncs.get_local_ip_address("web")
    vstring = cfuncs.app_version()
    
    return render_template('status.html', version=vstring, page_heading='System Status', title='Status', hostname = socket.gethostname(), ip = ip_address, ssid=ssid, quality=str(quality), level=str(level), no_sensors=no_sensors, sensors_list=all_sensors_list)   


@app.route("/about")
def about():
    vstring = cfuncs.app_version()
    return render_template('about.html', version=vstring, page_heading='About', title='About')


@app.route("/twentyfourhour_chart")
def twentyfourhour_chart():
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
               WHERE TEMP_READINGS.date_added >= (now() - INTERVAL 1 DAY)
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
    
    #formatted_data = str(data1).replace('\'', '')
    #print(formatted_data)
    #print(data1)
    
    cursor.close()
    db_conn.close()
    vstring = cfuncs.app_version()
    
    twenty4hoursbefore = datetime.datetime.now() - datetime.timedelta(days=1)
    now = datetime.datetime.now()
    xaxis_info = []
    xaxis_info.append("new Date(" + str(twenty4hoursbefore.year) + "," + str(twenty4hoursbefore.month) + "," + str(twenty4hoursbefore.day) + "," + str(twenty4hoursbefore.hour) + "," + str(twenty4hoursbefore.minute) + ")")
    xaxis_info.append("new Date(" + str(now.year) + "," + str(now.month) + "," + str(now.day) + "," + str(now.hour) + "," + str(now.minute) + ")")
    print("XAxis Min:  new Date(" + str(twenty4hoursbefore.year) + "," + str(twenty4hoursbefore.month) + "," + str(twenty4hoursbefore.day) + "," + str(twenty4hoursbefore.hour) + "," + str(twenty4hoursbefore.minute) + ")")
    print("XAxis Max:  new Date(" + str(now.year) + "," + str(now.month) + "," + str(now.day) + "," + str(now.hour) + "," + str(now.minute) + ")")
    
    page_title = '24hr Temps'
    chart_title = 'Temperature Readings for the last 24 hours'
    return render_template('time_line_chart.html',
                           version=vstring,
                           page_heading = '',
                           title=page_title,
                           temps1=str(data1).replace('\'', ''), 
                           temps2=str(data2).replace('\'', ''), 
                           temps3=str(data3).replace('\'', ''), 
                           series1=legend1, 
                           series2=legend2, 
                           series3=legend3,
                           chart_title=chart_title,
                           xaxis = xaxis_info)


@app.route("/today_chart")
def today_chart():
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
                           temps1=str(data1).replace('\'', ''), 
                           temps2=str(data2).replace('\'', ''), 
                           temps3=str(data3).replace('\'', ''), 
                           series1=legend1, 
                           series2=legend2, 
                           series3=legend3,
                           chart_title=chart_title,
                           xaxis = xaxis_info)


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
        
    page_title = 'Weekly Overview'
    chart_title1 = 'Weekly overview of Temperatures (' + all_sensor_aliases[0] + ')'
    chart_title2 = 'Weekly overview of Temperatures (' + all_sensor_aliases[1] + ')'
    chart_title3 = 'Weekly overview of Temperatures (' + all_sensor_aliases[2] + ')'
    return render_template('weekoverview_chart.html',
                           version=cfuncs.app_version(), title=page_title,
                           chart_title1=chart_title1,
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


def dump_all_db_data_out(db_cursor):
    query = "SELECT * FROM test.TEMP_READINGS"
    db_cursor.execute(query)

    for row in db_cursor.fetchall():
        id = str(row[0])
        date = str(row[1])
        temp = str(row[2])
        print(id + " " + date + " " + temp)


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
    print(sensor_ids)
    return no_of_sensors, sensor_ids


def clean_old_log_file():
    print("clean_old_log_file")
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

if __name__ == '__main__':
    clean_old_log_file()
    app.run(host='0.0.0.0', port=80, debug=True)
    
