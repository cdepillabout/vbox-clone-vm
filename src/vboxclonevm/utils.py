
"""
Various utilities for working with VirtualBox VMs and HDDs.
"""

import os
import re
import sys

from subprocess import Popen, PIPE

def storagetype(devuuid):
    """
    Return the storage type for the device with uuid devuuid.
    If the storage type is a host dvd, return the string "hostdvd".
    If the storage type is a host floppy, return the string "hostfloppy".
    If the storage type is a floppy, return the string "floppy".
    If the storage type is a dvd, return the string "dvd".
    If the storage type is a hdd, return the string "hdd".
    """
    listcommands = [
            ("hostdvds", "hostdvd"),
            ("hostfloppies", "hostfloppy"),
            ("floppies", "floppy"),
            ("dvds", "dvd"),
            ("hdds", "hdd"),
            ]

    for c, ret in listcommands:
        stdout = runcommand(["VBoxManage", "list", c])
        lines = stdout.strip().split('\n')
        for l in lines:
            m = re.match(r'^UUID:\s+%s$' % devuuid, l)
            if m:
                return ret
            else:
                continue

    return None

def runcommand(args):
    """
    Run a command and check stderr.  
    If anything is found on stderr, exit.
    Return stdout.
    """
    stdout, stderr = Popen(args, stdout=PIPE, stderr=PIPE).communicate()
    stdout = stdout.decode('utf-8')
    stderr = stderr.decode('utf-8')

    if stderr:
        print("ERROR! Could not run command %s:\n%s" % (args, stderr))
        sys.exit(1)

    warning = checkWarning(stdout)
    if warning:
        print(warning)
        sys.exit(1)

    return stdout

def checkWarning(stdout):
    """
    Checks the output of VBoxManage and makes sure there is no warning.
    Returns the warning string if there is a warning or None if no warning.
    """
    # is there a warning?
    m = re.match("^(WARNING: )", stdout)
    if not m:
        return None

    # return the warning text
    m = re.match("^(WARNING: )(.*?)(\nUUID:.*)?$", stdout, re.S)
    assert(len(m.groups()) >= 2)
    return m.group(1) + m.group(2)

def hddsattachedto(vm, hddforest):
    "Return a list of all hdds attached to a vm with a uuid of vmuuid."
    assert(type(vm) == type(""))
    return [hdd for hdd in hddforest.getends() if hdd.hdvm == vm or hdd.hdvmuuid == vm]
