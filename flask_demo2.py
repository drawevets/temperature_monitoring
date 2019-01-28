#! /usr/bin/python3.5

import common_functions as cfuncs
import datetime
import MySQLdb
import glob
from flask import Flask
from flask import render_template
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
#                                             Location   DB Name    DB Username   DB Passwd 
    db_conn = cfuncs.setup_db_connection("web", "localhost", "temps", "temps_reader", "reader")

    if db_conn is None:
        return("<html><h1>DB connection failed!</h1></html>")

    cursor = db_conn.cursor()
    sensor_names = []
    sensor_ids = []
    temp_readings = []
    current_datetime = []
    for sensor_name in all_sensors_list:
        db_sensor_id, offset = cfuncs.find_temp_sensor_id_and_offset(lg, db_conn, cursor, sensor_name, False)      
        if db_sensor_id is not None:
            temperature = cfuncs.read_temp(lg, sensor_name) + offset
            temperature = round(temperature,1)                          # Round to 1 decimal place
            sensor_names.append("TBC")
            sensor_ids.append(sensor_name)
            temp_readings.append(str(temperature))
            
            now = datetime.datetime.now()
            current_datetime.append(now.strftime("%d/%m/%y %X"))     # 24-Hour:Minute

    temp_details = list(zip(sensor_names, sensor_ids, temp_readings, current_datetime))

    #print(datetime.datetime.now())
    
    return render_template('home.html', version = vstring,
                                        page_heading = 'Current Temp Readings', 
                                        title = 'Home', 
                                        temp_data = temp_details)   


@app.route("/status")
def status():
    ssid, quality, level = cfuncs.check_wireless_network_connection(lg)
    all_sensors_list = cfuncs.find_all_temp_sensors_connected(lg)
    now = datetime.datetime.now()
    date_and_time = str(now.day) + "/"+ str(now.month).zfill(2) + "/" + str(now.year) + " " + str(now.hour).zfill(2) + ":" + str(now.minute).zfill(2) + ":" + str(now.second).zfill(2)
    ip_address = cfuncs.get_local_ip_address("web")
    vstring = cfuncs.app_version()
    
    return render_template('status.html', version=vstring, page_heading='System Status', title='Status', hostname = socket.gethostname(), ip = ip_address, ssid=ssid, quality=str(quality), level=str(level), no_sensors=str(len(all_sensors_list)), sensors_list=all_sensors_list)   


@app.route("/about")
def about():
    vstring = cfuncs.app_version()
    return render_template('about.html', version=vstring, page_heading='About', title='About')


@app.route("/time_chart")
def time_chart():
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

    query = """SELECT temp_sensor_db_id FROM temps.TEMP_READINGS 
               WHERE 
               DAYOFMONTH(TEMP_READINGS.date_added) = DAYOFMONTH(NOW())
               AND MONTH(TEMP_READINGS.date_added) = MONTH(NOW()) 
               AND YEAR(TEMP_READINGS.date_added) = YEAR(NOW())
               GROUP BY temp_sensor_db_id"""

    no_of_sensors, sensor_list = get_no_of_sensors_from_db_query(cursor, query)
    if no_of_sensors == 0:
        return("<html><h1>No temperature data for today yet!</h1></html>")

    if no_of_sensors != 3:
        return("<html><h1>Data for %d sensors found</h1><h1>Charting only works for 3 sensors currently!</h1></html>" % no_of_sensors)
    #print(sensor_list)
    
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
        if row[2] == 1:
            legend1 = str(row[3])
            data1.append("{x: new Date(" + row[0] + "), y: " + str(row[1]) +"}")
        if row[2] == 2:
            legend2 = str(row[3])
            data2.append("{x: new Date(" + row[0] + "), y: " + str(row[1]) +"}")
        if row[2] == 5:
            legend3 = str(row[3])
            data3.append("{x: new Date(" + row[0] + "), y: " + str(row[1]) +"}")
    
    #formatted_data = str(data1).replace('\'', '')

    #print("\nFormatted Date and time data:")
    #print(formatted_data)
    #print("\n")
    
    cursor.close()
    db_conn.close()
    vstring = cfuncs.app_version()
    
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
                           chart_title=chart_title)


@app.route("/today_chart")
def today_chart():
    #                              Location     DB Username   DB Passwd DB Name
    db_conn = cfuncs.setup_db_connection("localhost", "temps_reader", "reader", "temps")
    db_temp_readings_table = "TEMP_READINGS"
    if db_conn is None:
        return("<html><h1>DB connection failed!</h1></html>")

    cursor = db_conn.cursor()
    result = check_table_exists(cursor, db_temp_readings_table)

    if result is None:
        cursor.close()
        db_conn.close()
        return("<html><h1>TEMP_READINGS DB table does not exist!</h1></html>")

    query = """SELECT temp_sensor_db_id FROM temps.TEMP_READINGS 
               WHERE 
               DAYOFMONTH(TEMP_READINGS.date_added) = DAYOFMONTH(NOW())
               AND MONTH(TEMP_READINGS.date_added) = MONTH(NOW()) 
               AND YEAR(TEMP_READINGS.date_added) = YEAR(NOW())
               GROUP BY temp_sensor_db_id"""

    no_of_sensors, sensor_list = get_no_of_sensors_from_db_query(cursor, query)
    if no_of_sensors == 0:
        return("<html><h1>No temperature data for today yet!</h1></html>")

    if no_of_sensors != 3:
        return("<html><h1>Data for %d sensors found</h1><h1>Charting only works for 3 sensors currently!</h1></html>" % no_of_sensors)
    #print(sensor_list)
    
    query = """SELECT CONCAT(HOUR(TEMP_READINGS.date_added),':',MINUTE(TEMP_READINGS.date_added)) as time_added, 
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

    date_1 = []
    date_2 = []
    date_3 = []
    temps_1 = []
    temps_2 = []
    temps_3 = []
    for row in cursor.fetchall():
        if row[2] == 1:
            legend1 = str(row[3])
            date_1.append(str(row[0]))
            temps_1.append(row[1])
        if row[2] == 2:
            legend2 = str(row[3])
            date_2.append(str(row[0]))
            temps_2.append(row[1])
        if row[2] == 5:
            legend3 = str(row[3])
            date_3.append(str(row[0]))
            temps_3.append(row[1])
    cursor.close()
    db_conn.close()
    vstring = cfuncs.app_version()
    
    title = 'Old Today Only'
    return render_template('chart.html', version=vstring, values1=temps_1, values2=temps_2, values3=temps_3, labels=date_1, legend1=legend1, legend2=legend2, legend3=legend3, title=title)


@app.route('/overview')
def overview():
        #                              Location     DB Username   DB Passwd DB Name
        db_conn = cfuncs.setup_db_connection("localhost", "temps_reader", "reader", "temps")
        db_temp_readings_table = "TEMP_READINGS"
        if db_conn is None:
            print("DB connection failed!")
            #sys.exit(0)
        else:
            print("DB connection OK")

        #Setup a 'Cursor' to the Database connection
        cursor = db_conn.cursor()

        result = check_table_exists(cursor, db_temp_readings_table)

        if result is None:
            print("NO Table")
            cursor.close()
            db_conn.close()
            sys.exit(0)
        else:
            print("OK - Table exists")

        query = "SELECT DATE_FORMAT(date_added, '%d/%m/%y'), MIN(temperature), ROUND(AVG(temperature), 1), MAX(temperature) FROM temps.TEMP_READINGS GROUP BY DAYOFMONTH(date_added)"

        output = run_query_and_dump_out_overview(cursor, query, "Date Added   Min  Avg  Max")

        cursor.close()
        db_conn.close()
 
        return output


@app.route('/all')
def all():
        #                              Location     DB Username   DB Passwd DB Name
        db_conn = cfuncs.setup_db_connection("localhost", "temps_reader", "reader", "temps")
        db_temp_readings_table = "TEMP_READINGS"
        if db_conn is None:
            print("DB connection failed!")
            #sys.exit(0)
        else:
            print("DB connection OK")

        #Setup a 'Cursor' to the Database connection
        cursor = db_conn.cursor()

        result = check_table_exists(cursor, db_temp_readings_table)

        if result is None:
            print("NO Table")
            cursor.close()
            db_conn.close()
            sys.exit(0)
        else:
            print("OK - Table exists")

        #query = "SELECT * FROM temps.TEMP_READINGS ORDER BY temp_id DESC"
        query = "SELECT TEMP_READINGS.date_added, temp_sensor_alias, temperature FROM temps.TEMP_READINGS JOIN TEMP_SENSORS ON temp_sensor_db_id = TEMP_SENSORS.sensor_id ORDER BY temp_id DESC"

        output = run_query_and_dump_all_db_data_out(cursor, query, "All data recorded to date (last first)")

        cursor.close()
        db_conn.close()

        return output


@app.route('/last')
def last():
        #                              Location     DB Username   DB Passwd DB Name
        db_conn = cfuncs.setup_db_connection("localhost", "temps_reader", "reader", "temps")
        db_temp_readings_table = "TEMP_READINGS"
        if db_conn is None:
            print("DB connection failed!")
            #sys.exit(0)
        else:
            print("DB connection OK")

        #Setup a 'Cursor' to the Database connection
        cursor = db_conn.cursor()
    
        result = check_table_exists(cursor, db_temp_readings_table)

        if result is None:
            print("NO Table")
            cursor.close()
            db_conn.close()
            sys.exit(0)
        else:
            print("OK - Table exists")

        query = "SELECT * FROM temps.TEMP_READINGS"
    
        output = run_query_and_dump_last_entry_only(cursor, query, " id  datetime  sensor_id  sensor_name  temperature")

        cursor.close()
        db_conn.close()

        return output


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


def run_query_and_dump_last_entry_only(db_cursor, query, description):
    db_cursor.execute(query)
    for row in db_cursor.fetchall():
        id = str(row[0])
        datetime = str(row[1])
        sensor_id = str(row[2])
        temperature = str(row[3])
    all_data = "<html><h1> The last temperature reading was: " + temperature + " degC @ " + datetime + "</h1></html>"
    return all_data


def get_no_of_sensors_from_db_query(db_cursor, query_to_run):
    db_cursor.execute(query_to_run)
    no_of_sensors = db_cursor.rowcount

    sensor_ids = []
    for row in db_cursor.fetchall():
        sensor_ids.append(row[0])

    return no_of_sensors, sensor_ids


if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)
    
