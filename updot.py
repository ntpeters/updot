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
import time
import math

# Script version
updot_version = "1.2"
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

# Open manifest file, or create it if it doesn't exist
manifest = None
try:
    manifest = open(updot_dir + "/dotfiles.manifest", "r")
except IOError:
    print "\nManifest file not found!"
    print "Creating empty 'dotfiles.manifest'..."
    manifest = open( updot_dir + "/dotfiles.manifest", "w+" )
    manifest.write( "# updot.py Dotfile Manifest\n" )
    manifest.write( "# This file is used to define which dotfiles you want tracked with updot.py\n" )
    manifest.write( "# Add the path to each dotfile you wish to track below this line\n" )
    manifest.close();
    try:
        print "Opening in vim for user to edit..."
        time.sleep(1)
        check_call( ["notvim", "dotfiles.manifest"] )
        print "File contents updated by user.  Attempting to continue..."
        manifest = open( updot_dir + "/dotfiles.manifest", "r" )
    except OSError:
        print "\nVim not found. Unable to open manifest for user editing."
        print "Add to the manifest file the path of each dotfile you wish to track."
        print "Then run this script again."
        print "Exiting..."
        sys.exit();
    
# Check if dotfile directory exists, and create it if it doesn't
if not os.path.exists( dotfiles_dir ):
    print "\nDotfiles directory does not exist."
    print "Creating dotfiles directory..."
    os.makedirs( dotfiles_dir )
    
# Change to dotfiles repo directory
os.chdir(dotfiles_dir)


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

# Check for a readme, and create one if one doesn't exist
if not os.path.isfile( "README.md" ):
    #Create Readme file
    print "\nReadme not found."
    print "Creating readme file..."
    readme = open( "README.md", "w+" )
    readme.write( "dotfiles\n" )
    readme.write( "========\n" )
    readme.write( "My dotfiles repository.\n\n" )
    readme.write( "Created and maintained by the awesome 'updot.py' script!\n\n" )
    readme.write( "Get the script for yourself here: https://github.com/magrimes/updot\n" )
    readme.close()
    call( ["git", "add", dotfiles_dir + "/README.md"], stdout = outstream, stderr = errstream )


# Open timestamp file, or create it if it doesn't exist
timestamps = None
try:
    timestamps = open( dotfiles_dir + "/.timestamps", "r" )
except IOError:
    print "\nTimestamps file not found."
    print "Creating timestamps file..."
    timestamps = open( dotfiles_dir + "/.timestamps", "w+" )
    timestamps.close()
    call( ["git", "add", dotfiles_dir + "/.timestamps"], stdout = outstream, stderr = errstream )
    timestamps = open( dotfiles_dir + "/.timestamps", "r" )

# Process timestamps files, and update file modified times
print "\nRestoring file timestamps..."
file_timestamps = {}
for file_time in timestamps:
    split_str = file_time.split( "\t" )
    name = split_str[0]
    time = int( math.ceil( float( split_str[1][:-1] ) ) )
    file_timestamps[ name ] = time
    os.utime( name, (time,time) )

# Read manifest file
print "\nReading manifest file..."
files = {}
for path in manifest:
    # Don't process line if it is commented out
    if path[0] != "#":
        filename = path.split( "/" )[-1][:-1]
        files[ str(filename) ] = path

print "\nProcessing dotfiles...\n"

# copy each file to dotfiles
total_files = 0;
updated_files = 0;
invalid_files = 0;
new_files = 0;

no_update_files = 0;
non_existant_files = 0;

# Hold the file paths that need to be copied
# Key: src, Val: dest
update_remote = {}
update_local = {}
new_remote = {}
new_local = {}

for name, path in files.iteritems():
    path = string.rstrip(path, "\n")
    total_files += 1
    fullpath = os.path.expanduser(path)

    # Get local/remote times for comparison
    local_time = None
    remote_time = None
    try:
        local_time = int( math.ceil( float( os.path.getmtime( fullpath ) ) ) )
    except OSError:
        # File does not exist locally
        local_time = 0

    try:
        remote_time = int( file_timestamps[ name ] )
    except KeyError:
        # No timestamp exists for this file
        remote_time = 0

    if os.path.isfile(fullpath) or os.path.isdir(fullpath):
        filename_str = os.path.basename(fullpath)
        filename = dotfiles_dir + "/" + filename_str
        if os.path.isfile(filename) and os.path.isfile( fullpath ):
            # File is already in directory, and exists locally
            # Check if local is newer
            if local_time > remote_time:
                # Local is newer, mark for update
                update_remote[ fullpath ] = filename
                updated_files += 1
                file_timestamps[ name ] = local_time
            elif remote_time > local_time:
                # Remote file is newer than local, update local file
                update_local[ filename ] = fullpath
            else:
                # File times are the same, do nothing
                no_update_files += 1
        elif os.path.isfile( fullpath ):
            # File is not in directory, but does exist locally
            new_remote[ fullpath ] = filename
            new_files += 1
            file_timestamps[ name ] = local_time
        elif os.path.isfile( filename ):
            # File is in directory, but does not exist locally
            new_local[ filename ] = fullpath
        else:
            # The file does not exist locally or remotely, do nothing
            non_existant_files += 1
    else:
        total_files -= 1
        invalid_files += 1

# Save timestamps
timestamps.close()
timestamps = open( dotfiles_dir + "/.timestamps", "w" )
for path, time in file_timestamps.iteritems():
    timestamps.write( str(path) + "\t" + str(time) + "\n" )
timestamps.close()
call( ["git", "add", dotfiles_dir + "/.timestamps"], stdout = outstream, stderr = errstream )

remote_file_count = len( update_remote ) + len( new_remote )
if remote_file_count > 0:
    print "Remote files marked for update:"
# Update all changed remote files
for src, dest in update_remote.iteritems():
    filename_str = os.path.basename(src)
    call(["cp", "-v", src, dest], stdout = outstream, stderr = errstream )
    call(["git", "add", dest] )
    print "Updating " + filename_str + "..."

# Add all new remote files
for src, dest in new_remote.iteritems():
    filename_str = os.path.basename(src)
    call(["cp", "-v", src, dest], stdout = outstream, stderr = errstream )
    call(["git", "add", dest])
    print "Adding " + filename_str + "..."

local_file_count = len( update_local ) + len( new_local )
if local_file_count > 0:
    print "\nLocal files marked for update:"

for src, dest in update_local.iteritems():
    filename_str = os.path.basename(src)
    call(["cp", "-v", src, dest], stdout = outstream, stderr = errstream )
    print "Updating " + filename_str + "..."

for src, dest in new_local.iteritems():
    filename_str = os.path.basename(src)
    call(["cp", "-v", src, dest], stdout = outstream, stderr = errstream )
    print "Copying " + filename_str + "..."

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
