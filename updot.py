#!/usr/local/bin/python

# Author: Mike Grimes <magrimes@mtu.edu> 5-23-2013
#
# A script I made to automatically grab all of the dotfiles I want to keep
# track of, and push them upto my github repository. Files to be updated
# should be included in a 'dotfiles.manifest' file in the same directory
# as this script.

# open manifest file

from subprocess import call, check_output, check_call, CalledProcessError
import os
import string
import filecmp
import sys

github_username = "ntpeters"

updot_dir = os.path.dirname( os.path.abspath( __file__ ) ) 
user_home_dir = os.path.expanduser( "~" )
manifest = open(updot_dir + "/dotfiles.manifest", "r")
dotfiles_dir = user_home_dir + "/dotfiles"
# Check if dotfile directory exists, and create it if it doesn't
if not os.path.exists( dotfiles_dir ):
    print "\nCreating dotfiles directory...\n"
    os.makedirs( dotfiles_dir )

# Change to dotfiles repo directory
os.chdir(dotfiles_dir)

# Check if dotfiles directory is a git repo
try:
    check_call( ["git", "status"] )
except CalledProcessError:
    # Init as a local git repo
    print "\nInitializing local repository...\n"
    call( ["git", "init"] )

# Check if remote already added
try:
    check_call( ["git", "fetch", "origin", "master"] )
except CalledProcessError:
    print "\nNo remote repository found."
    print "Adding dotfiles remote...\n"
    # Check if repo already exists
    try:
        check_call( ["git", "remote", "add", "origin", "git@github.com:" + github_username + "/dotfiles.git"] )
        check_call( ["git", "fetch", "origin", "master"] )
    except CalledProcessError:
        print "\nRemote repository does not exist."
        print "Creating GitHub repository...\n"
        # Create repo on GitHub
        print "GitHub password required."
        call( ["curl", "-u", github_username, "https://api.github.com/user/repos", "-d", "{\"name\":\"dotfiles\"}"] )
        print "\nAdding dotiles remote...\n"
        call( ["git", "remote", "add", "origin", "git@github.com:" + github_username + "/dotfiles.git"] )

        print "\nCreating initial commit...\n"
        call( ["git", "add", ".", "-A"] )
        call( ["git", "commit", "-m", "\"Initial commit.\""] )
        call( ["git", "push", "origin", "master"] )

print "\nProcessing dotfiles...\n"

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
                print "Adding " + filename + "..."
                updated_files += 1
        else:
            # file is not in directory, we'll copy it and commit it
            new_files += 1
            call(["cp", "-v", fullpath, filename])
            call(["git", "add", filename])
            print "Adding " + filename + "..."
    else:
        total_files -= 1
        invalid_files += 1

if updated_files + new_files > 0:
    print "\nPushing changes...\n"
    call(["git", "commit", "-m", "updot.py update"])
    call(["git", "push", "origin", "master"])
else:
    print "Nothing to push."
    print "Everything up to date!"
