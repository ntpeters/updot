#!/usr/local/bin/python

# Author: Mike Grimes <magrimes@mtu.edu> 5-23-2013
#
# A script I made to automatically grab all of the dotfiles I want to keep
# track of, and push them upto my github repository. Files to be updated
# should be included in a 'dotfiles.manifest' file in the same directory
# as this script.

# open manifest file

from subprocess import call, check_output, check_call
import os
import string
import filecmp
import sys

updot_dir = os.path.dirname( os.path.abspath( __file__ ) ) 
user_home_dir = os.path.expanduser( "~" )
manifest = open(updot_dir + "/dotfiles.manifest", "r")
dotfiles_dir = user_home_dir + "/dotfiles"
# Check if dotfile directory exists, and create it if it doesn't
if not os.path.exists( dotfiles_dir ):
    os.makedirs( dotfiles_dir )

# Change to dotfiles repo directory
os.chdir(dotfiles_dir)

# Check if dotfiles directory is a git repo
try:
    check_call( ["git", "status"] )
except CalledProcessError:
    call( ["git", "init"] )

# copy each file to dotfiles
total_files = 0;
updated_files = 0;
invalid_files = 0;
new_files = 0;
# print "Copying files:"
for path in manifest:
    path = string.rstrip(path, "\n")
    total_files += 1
    fullpath = os.path.expanduser(path)
    # print fullpath

    if os.path.isfile(fullpath) or os.path.isdir(fullpath):
        filename = string.lstrip(os.path.basename(fullpath), ".")
        filename = dotfiles_dir + "/" + filename
        if os.path.isfile(filename):
        # file is already in directory, but before we update it
        # we first check if there are any changes to the file
            if not filecmp.cmp(fullpath, filename):
                # files are different, update
                call(["cp", "-v", fullpath, filename])
		call(["git", "add", filename])
		updated_files += 1
	else:
            # file is not in directory, we'll copy it and commit it
            new_files += 1
	    call(["cp", "-v", fullpath, filename])
	    call(["git", "add", filename])
    else:
        total_files -= 1
        invalid_files += 1

call(["git", "commit", "-m", "updot.py update"])
call(["git", "push"])
