
"""
Module that deals with VirtualBox VMs.  Provides the VM class and helper
functions.
"""

import os
import re
import sys

from vboxclonevm.hdd import createHDDForest
from vboxclonevm.utils import *

class VM:
    """
    An object that represents a VirtualBox VM.
    """
    def __init__(self, line, hddforest):
        self.hddforest = hddforest

        m = re.match(r'^"(.+?)" {([\w\d-]+)}$', line)
        assert(len(m.groups()) == 2)
        self.name = m.group(1)
        self.uuid = m.group(2)
        self.info = None

    def __str__(self):
        return "VM(name: %s, uuid: %s)" % (self.name, self.uuid)

    def __repr__(self):
        return self.__str__()

    def fillininfo(self):
        stdout = runcommand(["VBoxManage", "showvminfo", self.uuid, "--machinereadable"])
        lines = stdout.strip().split('\n')

        def create_values(line):
            def take_out_quotes(string):
                if len(string) <= 2:
                    return string
                if string[0] == '"':
                    string = string[1:]
                if string[-1] == '"':
                    string = string[:-1]
                return string

            key, value = line.strip().split('=')
            return take_out_quotes(key), take_out_quotes(value)

        self.info = {}
        for line in lines:
            key, value = create_values(line)

            # this is a hack because the value of firmware ("BIOS") is
            # capitalized when it should not be.
            if key.lower() == "firmware":
                value = value.lower()

            self.info[key.lower()] = value

    def __setoption(self, fromvm, option):
        """
        Set an option from another vm.  fromvm must have a dictionary
        "info" that has its options and values.
        
        Returns True if option was set, and False if not.
        """
        if option in fromvm.info.keys():
            runcommand(["VBoxManage", "modifyvm", self.uuid,
                "--%s" % option, "%s" % fromvm.info[option]])
            #print("Setting option --%s to \"%s\"" % (option, fromvm.info[option]))
            return True
        else:
            #print("Not setting option --%s because other vm does not have it set." % option)
            return False

    def __setstoragecontrolleroption(self, fromvm, name, stype, bootable):
        """
        Set a storage option from another vm.  fromvm must have a dictionary
        "info" that has its options and values.
        
        Returns True if option was set, and False if not.
        """
        vmoptions = fromvm.info.keys()
        if name in vmoptions and stype in vmoptions:
            cmdline = ["VBoxManage", "storagectl", self.uuid,
                "--name", fromvm.info[name], "--controller", fromvm.info[stype]]

            if bootable in vmoptions:
                cmdline.append("--bootable")
                cmdline.append(fromvm.info[bootable])

            contype = fromvm.info[stype]
            cmdline.append("--add")
            if contype in ["PIIX4", "PIIX3", "ICH6"]:
                cmdline.append("ide")
            elif contype in ["I82078"]:
                cmdline.append("floppy")
            elif contype in ["IntelAhci"]:
                cmdline.append("sata")
            elif contype in ["LsiLogic", "BusLogic"]:
                cmdline.append("scsi")
            elif contype in ["LSILogicSAS", "BusLogic"]:
                cmdline.append("sas")
            elif contype in ["unknown"]:
                #print("Not setting storage controller because type is unknown.")
                return True
            else:
                print("ERROR! Could not figure out controller type.")
                sys.exit(1)

            runcommand(cmdline)
            #print("Setting storrage controller option.")
            return True
        else:
            #print("Not setting storage controller because other vm does not have it set.")
            return False

    def __setstoragedevices(self, fromvm):
        """
        Set the storage devices from the new vm from the old vm, 
        cloning them if necessary.
        """
        cloned_hdds = 1
        # get all the storage controller name and type options
        nameopts = [opt for opt in fromvm.info.keys() if opt.startswith("storagecontrollername")]
        typeopts = [opt for opt in fromvm.info.keys() if opt.startswith("storagecontrollertype")]
        nameopts.sort()
        typeopts.sort()
        allopts = zip(nameopts, typeopts)
        #print()
        for nameopt, typeopt in allopts:
            name = fromvm.info[nameopt]
            taip = fromvm.info[typeopt]
            if taip == "unknown":
                # we don't know what do to with unknown devices
                print("Skipping unknown device...")
                continue
            #print("name: %s (%s), type: %s (%s)" % (name, nameopt, taip, typeopt))

            #controlleropts = [opt for opt in fromvm.info.keys() if opt.startswith(name.lower())]
            controlleropts = [opt for opt in fromvm.info.keys() if
                    re.match(r'^%s-\d\d?-\d\d?$' % name.lower(), opt)]
            for controlopt in controlleropts:
                if fromvm.info[controlopt] == "none":
                    # there is nothing here, just ignore it
                    #print("\t(none)")
                    continue

                # try to figure out whether this has an imageuuid varaiable associated with it
                m = re.match(r'^(.*?)-(\d\d?)-(\d\d?)$', controlopt)
                assert(m)
                tmpname = m.group(1)
                port = m.group(2)
                device = m.group(3)
                imageuuidopt = "%s-imageuuid-%s-%s" % (tmpname, port, device)
                imageuuid = None
                if imageuuidopt in fromvm.info:
                    imageuuid = fromvm.info[imageuuidopt]

                if fromvm.info[controlopt] == "emptydrive":
                    # attach empty drive
                    #print("\tAttaching empty device to %s... " % name)
                    cmdline = ["VBoxManage", "storageattach", self.uuid,
                        "--storagectl", name,
                        "--port", port,
                        "--device", device,
                        "--medium", "emptydrive"]
                    runcommand(cmdline)
                    continue

                #print("\t%s: %s" % (controlopt, fromvm.info[controlopt]))
                #print("\timageuuid: %s" % imageuuid)
                assert(imageuuid)

                strgtype = storagetype(imageuuid)
                #print("\tstorage type: %s" % strgtype)
                if strgtype in ["dvd", "floppy", "hostdvd", "hostfloppy"]:
                    #print("\tAttaching %s to %s... " % (strgtype, name))
                    cmdline = ["VBoxManage", "storageattach", self.uuid,
                        "--storagectl", name,
                        "--port", port,
                        "--device", device,]

                    cmdline.append("--medium")
                    if strgtype in ["hostdvd", "hostfloppy"]:
                        cmdline.append("host:%s" % imageuuid)
                    else:
                        cmdline.append("%s" % imageuuid)

                    cmdline.append("--type")
                    if strgtype in ["dvd", "hostdvd"]:
                        cmdline.append("dvddrive")
                    if strgtype in ["floppy", "hostfloppy"]:
                        cmdline.append("floppy")

                    runcommand(cmdline)
                    continue

                # it wasn't an empty drive, or a dvd/floppy drive, so it must be a hard drive
                assert(strgtype == "hdd")
                #print("fromvm: %s" % fromvm)
                #print("hddforest: %s" % self.hddforest)
                hdds = hddsattachedto(fromvm.uuid, self.hddforest)
                #print("hdds: %s" % hdds)

                # get the hdd whose uuid matches imageuuid
                tmphdds = [hdd for hdd in hdds if hdd.uuid == imageuuid]
                assert(len(tmphdds) == 1)
                hdd = tmphdds[0]
                #print("hdd: %s" % hdd)
                self.fillininfo()
                #print("self info: %s" % self.info)
                # just look for the config file and assume we 
                # can throw the hdd in the same dir
                configfile = self.info["cfgfile"]
                assert(os.path.isfile(configfile))
                dirname = os.path.dirname(configfile)

                newlocation = os.path.join(dirname, "%s-%s.vdi" % (self.name, cloned_hdds))
                cmdline = ["VBoxManage", "clonehd", hdd.uuid, newlocation]
                #print("cmdline: %s" % cmdline)
                stdout, stderr = Popen(cmdline, stdout=PIPE,
                        stderr=PIPE).communicate()
                stdout = stdout.decode('utf-8')
                stderr = stderr.decode('utf-8')

                if re.search("error", stderr, re.I):
                    print("ERROR! Could not run command %s:\n%s" % (cmdline, stderr))
                    sys.exit(1)

                cloned_hdds += 1

                newhddforest = createHDDForest()
                tmphdds = [hdd for hdd in newhddforest.values() if hdd.hdlocation == newlocation]
                assert(len(tmphdds) == 1)
                newhdd = tmphdds[0]
                #print("new hdd: %s" % [hdd for hdd in newhddforest.values() if hdd.hdlocation == newlocation])

                #print("Attaching new hard drive %s..." % newhdd.uuid)
                cmdline = ["VBoxManage", "storageattach", self.uuid,
                    "--storagectl", name,
                    "--port", port,
                    "--device", device,
                    "--medium", newhdd.uuid,
                    "--type", "hdd"]
                runcommand(cmdline)

    def setinfofrom(self, fromvm):
        "Copy the info from the other vm to this vm."
        options_to_copy = [
                "accelerate3d",
                "acpi",
                "audio",
                "boot1",
                "boot2",
                "boot3",
                "boot4",
                "clipboard",
                "cpus",
                "firmware",
                "guestmemoryballoon",
                "hpet"
                "hwvirtex",
                "hwvirtexexl",
                "ioacpi",
                "largepages",
                "memory",
                "monitorcount",
                "nextedpaging",
                "pae",
                "rtcseutc",
                "usb",
                "usbehci",
                "vram",
                "vrdeaddress",
                "vrdeauthtype",
                "vrdeauthtype",
                "vrdemulticon",
                "vrdeport",
                "vrdereusecon",
                "vrdevideochannel",
                "vrdevideochannelquality",
                "vtxvpid",
                ]

        sys.stdout.write("Setting options for new VM from old VM (this may take a while)... ")
        sys.stdout.flush()

        for option in options_to_copy:
            self.__setoption(fromvm, option)

        print("Done.")
        sys.stdout.write("Setting network options for new VM from old VM... ")
        sys.stdout.flush()

        multi_options_to_copy = [
                "nic",
                "nictype",
                "cableconnected",
                "bridgeadapter",
                "hostonlyadapter",
                "intnet",
                "vdenet",
                "natnet",
                ]

        # continue trying to set options until we get to a round where no options are set
        i = 1
        while True:
            did_set_list = []
            for option in multi_options_to_copy:
                did_set_list.append(self.__setoption(fromvm, "%s%d" % (option, i)))
            if not any(did_set_list):
                break
            i += 1

        print("Done.")
        sys.stdout.write("Setting storage controller options for new VM from old VM... ")
        sys.stdout.flush()

        i = 0
        did_set_option = True
        while did_set_option:
            did_set_option = self.__setstoragecontrolleroption(fromvm,
                    "storagecontrollername%d" %  i,
                    "storagecontrollertype%d" %  i,
                    "storagecontrollerbootable%d" %  i)
            i += 1

        print("Done.")
        sys.stdout.write("Copying storage devices for new VM from old VM (this may take a long time)... ")
        sys.stdout.flush()

        self.__setstoragedevices(fromvm)

        print("Done.")

def createNewVM(name, ostype, hddforest):
    "Create a new VM with name and ostype.  Return new vm."

    sys.stdout.write("Creating new vm... ")
    runcommand(["VBoxManage", "createvm", "--name", name, "--register", "--ostype", ostype])
    print("Done.")
    return getVM(hddforest, name)

def getVM(hddforest, vmname=None):
    """
    Get a vm, or a list of all vms.  If vmname is None, then we
    just get a list of all VMs.  If vmname is specified, then 
    we return just the named vm.
    
    This does not return snapshots.
    """
    stdout = runcommand(["VBoxManage", "list", "vms"])
    stdout = stdout.strip()
    lines = stdout.split('\n')
    vms = [VM(l, hddforest) for l in lines]
    if not vmname:
        return vms
    named_vms = [vm for vm in vms if vm.name == vmname or vm.uuid == vmname]
    assert(len(named_vms) == 1)
    return named_vms[0]
