
"""
Module that deals with VirtualBox hard disks.  Provides both HDD class and
Forest class.
"""

import os
import re
import sys

from vboxclonevm.utils import *

class HDD:
    """
    Create a vdi entry from the output of `VBoxManage list hdds`.
    """
    def __init__(self, lines, forest=None, parent=None):
        """
        Initialize an hdd.  lines is a list of the 7 lines of output
        from `VBoxManage list hdds`.  forest is a Forest object or None.
        parent is the parent HDD object or None.
        """
        assert(len(lines) >= 6)

        self.uuid = re.sub(r'^UUID:\W+', '', lines[0])
        self.parentuuid = re.sub(r'^Parent UUID:\W+', '', lines[1])
        self.hdformat = re.sub(r'^Format:\W+', '', lines[2])
        self.hdlocation = re.sub(r'^Location:\s+', '', lines[3])
        self.hdstate = re.sub(r'^State:\W+', '', lines[4])
        self.hdtype = re.sub(r'^Type:\W+', '', lines[5])

        self.hdusage = None
        self.hdvm = None
        self.hdvmuuid = None
        self.hdsnapshot = None
        self.hdsnapshotuuid = None
        if len(lines) == 7:
            self.hdusage = re.sub(r'^Usage:\W+', '', lines[6])

            m = re.match(r'^(.*?) \(UUID: ([\w\d-]+)\)$', self.hdusage)
            if not m:
                m = re.match(r'^(.*?) \(UUID: ([\w\d-]+)\) \[(.*?) \(UUID: ([\w\d-]+)\)\]$', self.hdusage)
                if not m:
                    print("Couldn't get usage information for hd %s: %s" % (self.uuid, self.hdusage))
                    sys.exit(1)

            assert(len(m.groups()) >= 2)
            self.hdvm = m.group(1)
            self.hdvmuuid = m.group(2)
            if len(m.groups()) == 4:
                self.hdsnapshot = m.group(3)
                self.hdsnapshotuuid = m.group(4)

        self.forest = forest
        self.parent = parent

    def __str__(self):
        string = ""
        string += "uuid: %s\n" % self.uuid
        string += "parent: %s\n" % self.parentuuid
        string += "format: %s\n" % self.hdformat
        string += "location: %s\n" % self.hdlocation
        string += "state: %s\n" % self.hdstate
        string += "type: %s\n" % self.hdtype
        if self.hdvm:
            #string += "usage: %s\n" % self.hdusage
            string += "vm: %s (%s)\n" % (self.hdvmuuid, self.hdvm)
            if self.hdsnapshot:
                string += "snapshot: %s (%s)\n" % (self.hdsnapshotuuid, self.hdsnapshot)

        if self.parent:
            string += "(parent: %s)\n" % self.parent.uuid
        if self.forest and self.forest.getChildren(self.uuid):
            string += "(children: %s)\n" % [child.uuid for child in self.forest.getChildren(self.uuid)]
        return string

    def __repr__(self):
        return self.__str__()

class Forest:
    """
    Forest of multiple trees of unique nodes.
    Each node needs to have a uuid and parent member."""

    def __init__(self):
        self.nodes = {}

    def __getitem__(self, key):
        return self.nodes[key]

    def __setitem__(self, key, new_node):
        assert(key == new_node.uuid)
        for n in self.nodes.values():
            if n.parentuuid == new_node.uuid:
                n.parent = new_node
            if n.uuid == new_node.parentuuid:
                new_node.parent = n
        self.nodes[key] = new_node

    def __contains__(self, key):
        return self.nodes.__contains__(key)

    def __iter__(self):
        return self.nodes.__iter__()

    def __len__(self):
        return len(self.nodes)

    def __str__(self):
        string = "%s nodes\n" % len(self.nodes)
        for node in self.nodes.values():
            string += "%s\n" % node

        return string

    def items(self):
        return self.nodes.items()

    def values(self):
        return self.nodes.values()

    def getends(self):
        "Return a list of nodes in forest that have no children."
        return [n for n in self.nodes.values() if not self.getChildren(n.uuid)]

    def getChildren(self, parent_node_uuid):
        """
        Return list of children for the parent node. parent_node_uuid is
        just a string of the parent node's uuid.
        """
        assert(type(parent_node_uuid) != type(HDD))
        return [n for n in self.nodes.values() if n.parentuuid == parent_node_uuid]

def createHDDForest():
    """
    Return a Forest() object of all hdds available.
    This does not include snapshots.
    """
    stdout = runcommand(["VBoxManage", "list", "hdds"])
    stdout = stdout.strip()
    lines = stdout.split("\n\n")

    if len(lines) == 0:
        print("ERROR: No hdds.")
        sys.exit(1)

    forest = Forest()
    for l in lines:
        hdd = HDD(l.strip().split("\n"), forest)
        forest[hdd.uuid] = hdd

    return forest
