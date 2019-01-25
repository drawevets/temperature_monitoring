#! /usr/bin/python3.5

import datetime
import MySQLdb
import glob
from flask import Flask
from flask import render_template
import subprocess

app = Flask(__name__)

#Example of charting: https://www.patricksoftwareblog.com/creating-charts-with-chart-js-in-a-flask-application/
#
#For Chart.js source goto link:
#https://github.com/chartjs/Chart.js/releases/latest

@app.route("/")
@app.route("/home")
def home():
    ssid, quality, level = check_wireless_network_connection()
    all_sensors_list = find_all_temp_sensors_connected()
    now = datetime.datetime.now()
    date_and_time = str(now.day) + "/"+ str(now.month).zfill(2) + "/" + str(now.year) + " " + str(now.hour).zfill(2) + ":" + str(now.minute).zfill(2) + ":" + str(now.second).zfill(2)
    ip_address = get_local_ip_address()
    
    html_return = "<html><h1>Temperature Monitoring System Status Page</h1></br>"
    html_return += "<h3>Wireless Network Connection SSID: " + ssid + "</h3>"
    html_return += "<h3>Wireless Network Signal Quality:  " + str(quality) + "%</h3>"
    html_return += "<h3>Wireless Network Signal Level:    " + str(level) + "dB</h3></br>"
    html_return += "<h2>There are " + str(len(all_sensors_list)) + " sensors connected: </h2>"
    for sensor in all_sensors_list:
        html_return += "<h2>" + sensor + "</h2>"
    html_return += "</br><h3>This is <a href=http://" + ip_address + ":5000/today_chart>today's chart</h3></a>"
    html_return += "</br><body><i>(Status as of  " + date_and_time + ")</i><body>"
    html_return += "</html>"
    return render_template('home.html', title='Home', ssid=ssid, quality=str(quality), level=str(level), no_sensors=str(len(all_sensors_list)), sensors_list=all_sensors_list)   
    #return(html_return)


@app.route("/about")
def about():
    return render_template('about.html', title='About')


@app.route("/time_chart")
def time_chart():
    #                              Location     DB Username   DB Passwd DB Name
    db_conn = setup_db_connection("localhost", "temps_reader", "reader", "temps")
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
    data = []

    for row in cursor.fetchall():
        if row[2] == 1:
            legend = str(row[3])
            date.append(str(row[0]))
            temps.append(row[1])
            data.append("{x: new Date(" + row[0] + "), y: " + str(row[1]) +"}")
    
    formatted_data = str(data).replace('\'', '')

    #print("\nFormatted Date and time data:")
    #print(formatted_data)
    #print("\n")
    
    cursor.close()
    db_conn.close()

    title = 'Today Only'
    return render_template('time_line_chart.html', time_data=formatted_data, values=temps, labels=date, legend=legend, title=title)


@app.route("/today_chart")
def today_chart():
    #                              Location     DB Username   DB Passwd DB Name
    db_conn = setup_db_connection("localhost", "temps_reader", "reader", "temps")
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
    
    title = 'Old Today Only'
    return render_template('chart.html', values1=temps_1, values2=temps_2, values3=temps_3, labels=date_1, legend1=legend1, legend2=legend2, legend3=legend3, title=title)


@app.route('/overview')
def overview():
        #                              Location     DB Username   DB Passwd DB Name
        db_conn = setup_db_connection("localhost", "temps_reader", "reader", "temps")
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
        db_conn = setup_db_connection("localhost", "temps_reader", "reader", "temps")
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
        db_conn = setup_db_connection("localhost", "temps_reader", "reader", "temps")
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


def setup_db_connection(host, user, passwd, db):
    #Connect to Database
    try:
        db = MySQLdb.connect(host, user, passwd, db)
    except:
        print("Database connection failed!")
        db = None
    return db


def check_table_exists(db_cursor, table_name):
    #print("Checking whether the " + table_name + " table already exists")

    table_check = "SHOW TABLES LIKE '%" + table_name + "%'"
    db_cursor.execute(table_check)
    #print("Rows returned: " + str(cursor.rowcount))
    return db_cursor.fetchone()                         # this will be None for none existent table


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


def find_all_temp_sensors_connected():
    all_sensors_list = []
    devices = glob.glob('/sys/bus/w1/devices/' + '28*')
    #write_to_log(">> find_all_temp_sensors_connected()")
    count = 0
    if len(devices):
        #write_to_log("   " + str(len(devices)) + " sensor(s) found:")
        for count, sensor in enumerate(devices):
            sensor_name = sensor.strip()[-15:]
            #write_to_log("     " + sensor.strip()[-15:])
            all_sensors_list.append(sensor_name)
    else:
        #write_to_log("   No Sensors found!")
        all_sensors_list = None      
    #write_to_log("<< find_all_temp_sensors_connected()")
    return all_sensors_list


def check_wireless_network_connection():
    #write_to_log(">> check_wireless_network_connection()")
    ssid = ''
    quality = 0
    level = 0
    result = None
    #ps = subprocess.Popen(['iwconfig'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    ps = subprocess.Popen(['iwlist', 'wlan0', 'scan'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
        outbytes = subprocess.check_output(('grep', 'ESSID'), stdin=ps.stdout)
        output = str(outbytes)
        find_start_of_ssid = output[output.find('ESSID:')+7:len(output)]
        ssid = find_start_of_ssid[0:find_start_of_ssid.find('"')]
        #write_to_log("   WiFi SSID: " + ssid)
        result = 0
    except subprocess.CalledProcessError:
        # grep did not match any lines
        print("ERROR    No wireless networks connected!!")

    if result is not None:
        ps = subprocess.Popen(['iwlist', 'wlan0', 'scan'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)    
        outbytes = subprocess.check_output(('grep', 'Quality'), stdin=ps.stdout)
        output = str(outbytes)
        pos = output.find('Quality=')
        quality_str = output[pos+len('Quality='):len(output)]
        quality_str = quality_str[0:2]
        quality = int((float(quality_str) / 70.0) * 100.0)
        #write_to_log("   WiFi Signal quality: " + str(quality) + "%")

        pos = output.find('Signal level=')
        level_str = output[pos+len('Signal level='):len(output)]
        level_str = level_str[0:3]
        level = int(level_str)
        #write_to_log("   WiFi Signal Level: " + str(level) + "dBm")

    #write_to_log("<< check_wireless_network_connection()")
    return ssid, quality, level


def get_local_ip_address():
    ip_address = "No network"
    ps = subprocess.Popen(['ifconfig'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
        outbytes = subprocess.check_output(('grep', '-A 1', 'wlan0'), stdin=ps.stdout)
        output = str(outbytes)
        #print(output)
        find_start_of_ip = output[output.find('inet ')+5:len(output)]
        ip_address = find_start_of_ip[0:find_start_of_ip.find(' ')]
        #write_to_log("   IP Address: " + ip_address)
        #time.sleep(1)
    except subprocess.CalledProcessError:
        time.sleep(0.2)  #Do nothing!!
    return ip_address


if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)
