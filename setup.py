#!/usr/bin/env python3

from distutils.core import setup

setup(name='vbox-clone-vm',
      version='1.0',
      description='Clone a VirtualBox vm, including vm settings and disks.',
      author='(cdep) illabout',
      author_email='cdep.illabout@gmail.com',
      #url='http://www.python.org/sigs/distutils-sig/',
      scripts=['src/vbox-clone-vm'],
      data_files=[('etc/bash_completion.d', ['datafiles/bash_completion.d/vbox-clone-vm'])],
     )

