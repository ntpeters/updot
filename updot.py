#!/usr/local/bin/python

# Author: Mike Grimes   <magrimes@mtu.edu>  5-23-2013
#         Nate Peterson <ntpeters@mtu.edu>  12-1-2013
#
# A script I made to automatically grab all of the dotfiles I want to keep
# track of, and push them upto my github repository. Files to be updated
# should be included in a 'dotfiles.manifest' file in the same directory
# as this script.

from subprocess import call, check_output, check_call, CalledProcessError
import os
import string
import filecmp
import sys

# Script version
updot_version = "1.1"
print "updot v" + updot_version + " - Dotfile update script"

# When false, unnecessary output is suppressed
debug = False

# Open output streams
devnull = open( os.devnull, "w" )
stdout  = sys.stdout
stderr  = sys.stderr

# Set active output stream
outstream = None
errstream = None
if debug:
    outstream = stdout
    errstream = stderr
else:
    outstream = devnull
    errstream = devnull

# Set GitHub username
github_username = ""

# Try to get GitHub username from git config
try:
    github_username = check_output( ["git", "config", "github.user"] )[:-1]
except CalledProcessError:
   print "\nGitHub user entry does not exist in git config, creating now..."
   call( ["git", "config", "--global", "github.user", ""], stdout = outstream, stderr = errstream )

# Check if GitHub username has been set
if len( github_username ) == 0:
    print "\nNo GitHub username found. Please provide one now."
    github_username = raw_input( 'Enter GitHub username: ' )
    print "Storing username in git config."
    call( ["git", "config", "--global", "github.user", github_username], stdout = outstream, stderr = errstream )

# Setup directory variables
updot_dir = os.path.dirname( os.path.abspath( __file__ ) ) 
user_home_dir = os.path.expanduser( "~" )
dotfiles_dir = user_home_dir + "/dotfiles"

# Open manifest file
manifest = open(updot_dir + "/dotfiles.manifest", "r")

# Check if dotfile directory exists, and create it if it doesn't
if not os.path.exists( dotfiles_dir ):
    print "\nDotfiles directory does not exist."
    print "Creating dotfiles directory..."
    os.makedirs( dotfiles_dir )
    
# Change to dotfiles repo directory
os.chdir(dotfiles_dir)

if not os.path.isfile( "README.md" ):
    #Create Readme file
    print "\nReadme not found."
    print "Creating readme file..."
    readme = open( "README.md", "w+" )
    readme.write( "dotfiles\n" )
    readme.write( "========\n" )
    readme.write( "My dotfiles repository.\n\n" )
    readme.write( "Created by the awesome 'updot.py' script!\n\n" )
    readme.write( "Get the script for yourself here: https://github.com/magrimes/updot\n" )
    readme.close()

# Check if dotfiles directory is a git repo
try:
    check_call( ["git", "status"], stdout = outstream, stderr = errstream )
except CalledProcessError:
    # Init as a local git repo
    print "\nDotfiles directory does not contain a git repository."
    print "Initializing local repository..."
    call( ["git", "init"], stdout = outstream, stderr = errstream )

# Check if remote already added
try:
    check_call( ["git", "fetch", "origin", "master"], stdout = outstream, stderr = errstream )
except CalledProcessError:
    print "\nNo remote repository found."
    print "Adding dotfiles remote..."
    # Check if repo already exists
    try:
        check_call( ["git", "remote", "add", "origin", "git@github.com:" + github_username + "/dotfiles.git"], stdout = outstream, stderr = errstream )
        check_call( ["git", "fetch", "origin", "master"], stdout = errstream, stderr = outstream )
    except CalledProcessError:
        print "\nRemote repository does not exist."
        print "Creating GitHub repository...\n"

        # Suppress curl ouput
        silentflag = ""
        if not debug:
            silentflag = "-s"

        # Create repo on GitHub
        print "GitHub password required."
        call( ["curl", silentflag, "-u", github_username, "https://api.github.com/user/repos", "-d", "{\"name\":\"dotfiles\", \"description\":\"My dotfiles repository\"}"], stdout = outstream )
        print "\nAdding dotfiles remote..."
        call( ["git", "remote", "add", "origin", "git@github.com:" + github_username + "/dotfiles.git"], stdout = outstream, stderr = errstream )

        print "\nCreating initial commit..."
        call( ["git", "add", ".", "-A"], stdout = outstream, stderr = errstream )
        call( ["git", "commit", "-m", "\"Initial commit.\""], stdout = outstream, stderr = errstream)
        call( ["git", "push", "origin", "master"], stdout = outstream, stderr = errstream )

# Pull most recent files from remote repository for comparison
print "\nPulling most recent revisions from remote repository..."
call( ["git", "pull", "origin", "master"], stdout = outstream, stderr = errstream )

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
        filename_str = string.lstrip(os.path.basename(fullpath), ".")
        filename = dotfiles_dir + "/" + filename_str
        if os.path.isfile(filename):
            # file is already in directory, but before we update it
            # we first check if there are any changes to the file
            if not filecmp.cmp(fullpath, filename):
                # files are different, update
                call(["cp", "-v", fullpath, filename], stdout = outstream, stderr = errstream )
                call(["git", "add", filename] )
                print "Updating " + filename_str + "..."
                updated_files += 1
        else:
            # file is not in directory, we'll copy it and commit it
            new_files += 1
            call(["cp", "-v", fullpath, filename], stdout = outstream, stderr = errstream )
            call(["git", "add", filename])
            print "Adding " + filename_str + "..."
    else:
        total_files -= 1
        invalid_files += 1

push_files = updated_files + new_files

if push_files > 0:
    print "\nPushing changes...\n"
    try:
        check_call(["git", "commit", "-m", "updot.py update"], stdout = outstream, stderr = errstream )
        check_call(["git", "push", "origin", "master"], stdout = outstream, stderr = errstream )
        print "Push successful!"
        print "Updated " + str( push_files ) + " files successfully!"
        print "All remote files up to date!"
    except CalledProcessError:
        print "Error pushing changes!"
else:
    print "Nothing to push."
    print "Everything up to date!"
