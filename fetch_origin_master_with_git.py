#! /usr/bin/python3.5
#Should probably add a check for network signal etc before attempting this in the real world??

###################################################################
# https://amoffat.github.io/sh/index.html
# sh - is a full-fledged subprocess replacement for Python
#     that allows you to call any program as if it were a function:
import sh
from sh import git
###################################################################

import time
import os, sys

def CheckForUpdate(workingDir):
    print("Fetching most recent code from source..." + workingDir)

    # Fetch most up to date version of code.
    #p = git("--git-dir=" + workingDir + ".git/", "--work-tree=" + workingDir, "fetch", "origin", "master", _out=ProcessFetch, _out_bufsize=0, _tty_in=True)               
    p = git("--git-dir=" + workingDir + ".git/", "--work-tree=" + workingDir, "fetch", "origin", "master", _out_bufsize=0, _tty_in=True)               
    
    print("Fetch complete.")
    time.sleep(2)
    print("Checking status for " + workingDir + "...")
    statusCheck = git("--git-dir=" + workingDir + ".git/", "--work-tree=" + workingDir, "status")

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
        print("Check complete")
        os.system("shutdown -r 1")
