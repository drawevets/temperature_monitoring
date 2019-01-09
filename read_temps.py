#!/usr/bin/python3.5
#Now in git also

import os
import MySQLdb
import sys
import time

def setup_db_connection(host, user, passwd, db):
    #Connect to Database
    try:
        db = MySQLdb.connect(host, user, passwd, db)
    except:
        print("Database connection failed!")
        db = None
    return db


def check_table_exists(db_cursor, table_name):
    print("Checking whether the " + table_name + " table already exists")

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
    print("Running Query: " + query)
    db_cursor.execute(query)

    print("\n" + description)
    for row in db_cursor.fetchall():
        print(row)
        #id = str(row[0])
        #date = str(row[1])
        #temp = str(row[2])
        #print(id + " " + date + " " + temp)


def main():

    while True:
        os.system('clear')

        #                              Location     DB Username   DB Passwd DB Name
        db_conn = setup_db_connection("localhost", "temp_reader", "reader", "test")
        db_temp_readings_table = "TEMP_READINGS"
        if db_conn is None:
            print("DB connection failed!")
            sys.exit(0)
        else:
            print("DB connection OK")
        global Global_db_conn
        Global_db_conn = db_conn

        #Setup a 'Cursor' to the Database connection
        cursor = db_conn.cursor()
        global Global_db_cursor
        Global_db_cursor = cursor

        #Setup a Query
        #query = "SELECT * FROM test.temps WHERE date_of_reading < STR_TO_DATE('24/12/2018 17:00', '%d/%m/%Y %H:%i') "
        #print("Intentionally removing temp readings table")
        #cursor.execute("DROP TABLE IF EXISTS TEMP_READINGS")

        result = check_table_exists(cursor, db_temp_readings_table)

        if result is None:
            print("NO Table")
            cursor.close()
            db_conn.close()
            sys.exit(0)
        else:
            print("OK - Table exists")

        query = "SELECT DATE_FORMAT(date_added, '%d/%m/%y'), MIN(temperature), ROUND(AVG(temperature), 1), MAX(temperature) FROM test.TEMP_READINGS GROUP BY DAYOFMONTH(date_added)"
        
        run_query_and_dump_all_db_data_out(cursor, query, "Date Added   Min  Avg  Max")

        cursor.close()
        db_conn.close()
        time.sleep(30)

########################################################################################################

main()
