#! /usr/bin/python3.5
#Should probably add a check for network signal etc before attempting this in the real world??

###################################################################
# https://amoffat.github.io/sh/index.html
# sh - is a full-fledged subprocess replacement for Python
#     that allows you to call any program as if it were a function:
import sh
from sh import git
###################################################################
import datetime
import time
import os, sys

def CheckForUpdate(workingDir):
    print("Fetching most recent code from source..." + workingDir)

    # Fetch most up to date version of code.
    #p = git("--git-dir=" + workingDir + ".git/", "--work-tree=" + workingDir, "fetch", "origin", "master", _out=ProcessFetch, _out_bufsize=0, _tty_in=True)               
    p = git("--git-dir=" + workingDir + ".git/", "--work-tree=" + workingDir, "fetch", "origin", "master", _out_bufsize=0, _tty_in=True)               
    print(p)
    print("Fetch complete.")
    time.sleep(2)
    print("Checking status for " + workingDir + "...")
    statusCheck = git("--git-dir=" + workingDir + ".git/", "--work-tree=" + workingDir, "status")
    print(statusCheck)
    if "Your branch is up-to-date" in statusCheck:
        print("Status check passes.")
        print("Code up to date.")
        return False
    else:
        print("Code update available.")
        return True


if __name__ == "__main__":

    gitDir = "/home/steve/temperature_monitoring/"

    print("*********** Checking for code update **************")
    
    if CheckForUpdate(gitDir):
        print("Resetting code...")
        resetCheck = git("--git-dir=" + gitDir + ".git/", "--work-tree=" + gitDir, "reset", "--hard", "origin/master")
        print(str(resetCheck))
        last_change_str = str(resetCheck).split('HEAD is now at ')
        print("Last change: " + str(last_change_str[1]))

        try:
            change_file =  open("/home/steve/temperature_monitoring/last_change.txt", 'w')
            now = datetime.datetime.now()
            log_date = str(now.day).zfill(2) + "/"+ str(now.month).zfill(2) + "/" + str(now.year) + " " + str(now.hour).zfill(2) + ":" + str(now.minute).zfill(2) + ":" + str(now.second).zfill(2) + " "
            log_string = log_date + " " + str(last_change_str[1])
            print(log_string)
            change_file.close()
        except:
            print("Failed to write to /home/steve/temperature_monitoring/last_change.txt")
            
        print("Check complete.....reseting now....")
        #os.system("/sbin/shutdown -r 0")
