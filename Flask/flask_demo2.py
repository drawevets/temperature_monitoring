#! /usr/bin/python3.5

import MySQLdb

from flask import Flask
from flask import render_template
app = Flask(__name__)

#Example of charting: https://www.patricksoftwareblog.com/creating-charts-with-chart-js-in-a-flask-application/
#
#For Chart.js source goto link:
#https://github.com/chartjs/Chart.js/releases/latest

@app.route("/all_chart")
def all_chart():
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

    query = "SELECT * FROM temps.TEMP_READINGS ORDER BY temp_id ASC"
    cursor.execute(query)
    id = []
    temperature = []
    for row in cursor.fetchall():
        id.append(str(row[1]))
        temperature.append(row[4])
    cursor.close()
    db_conn.close()

    title = 'All Recorded Temperatures'
    legend = 'Temperatures'
    return render_template('chart.html', values=temperature, labels=id, legend=legend, title=title)

@app.route("/day_chart")
def day_chart():
    #                              Location     DB Username   DB Passwd DB Name
    db_conn = setup_db_connection("localhost", "temps_reader", "reader", "temps")
    db_temp_readings_table = "TEMP_READINGS"
    if db_conn is None:
        #print("DB connection failed!")
        sys.exit(0)
    #else:
        #print("DB connection OK")

    cursor = db_conn.cursor()

    result = check_table_exists(cursor, db_temp_readings_table)

    if result is None:
        cursor.close()
        db_conn.close()
        sys.exit(0)
    #else:
        #print("OK - Table exists")

    query = """SELECT CONCAT(HOUR(TEMP_READINGS.date_added),MINUTE(TEMP_READINGS.date_added)) as time_added, 
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

    title = 'All Temperature Sensor Readings Today'
    return render_template('chart.html', values1=temps_1, values2=temps_2, values3=temps_3, labels=date_1, legend1=legend1, legend2=legend2, legend3=legend3, title=title)


@app.route('/')
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


if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)
