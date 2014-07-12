#!/usr/local/bin/python

# Authors:  Mike Grimes   <magrimes@mtu.edu>
#           Nate Peterson <ntpeters@mtu.edu>
#
# A script made to automatically grab all of the dotfiles a user desires to
# keep track of, and keep them synced with their github repository.
# Files to be updated should be included in a 'dotfiles.manifest' file in the
# 'dotfiles' directory that this script will create in your home directory.

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
debug = True

# Open output streams
devnull = open( os.devnull, "w" )
stdout  = sys.stdout
stderr  = sys.stderr

# Set active output stream
outstream = devnull
errstream = devnull
if debug:
    outstream = stdout
    errstream = stderr

# Set GitHub username
github_username = ""

# Try to get GitHub username from git config
print "\nAttempting to retrieve GitHub username..."
try:
    github_username = check_output( ["git", "config", "github.user"] )[:-1]
except CalledProcessError:
   print "GitHub user entry does not exist in git config, creating now..."
   call( ["git", "config", "--global", "github.user", ""], stdout = outstream, stderr = errstream )

# Check if GitHub username has been set
if len( github_username ) == 0:
    print "No GitHub username found. Please provide one now."
    github_username = raw_input( 'Enter GitHub username: ' )
    print "Storing username in git config."
    call( ["git", "config", "--global", "github.user", github_username], stdout = outstream, stderr = errstream )

print "GitHub Username: " + github_username

# Setup directory variables
updot_dir = os.path.dirname( os.path.abspath( __file__ ) )
user_home_dir = os.path.expanduser( "~" )
dotfiles_dir = user_home_dir + "/dotfiles"

# Check if dotfile directory exists, and create it if it doesn't
print "\nChecking for '~/dotfiles' directory..."
if not os.path.exists( dotfiles_dir ):
    print "Dotfiles directory does not exist."
    print "Creating dotfiles directory..."
    os.makedirs( dotfiles_dir )
else:
    print "Dotfiles directory exists!"

# Open manifest file, or create it if it doesn't exist
print "\nChecking for 'dotfiles.manifest'..."
manifest_dir = dotfiles_dir + "/dotfiles.manifest"
manifest = None
try:
    manifest = open(manifest_dir, "r")
    print "Manifest file exists!"
except IOError:
    print "Manifest file not found!"
    print "Creating empty 'dotfiles.manifest'..."
    manifest = open( manifest_dir, "w+" )
    manifest.write( "# updot.py Dotfile Manifest\n" )
    manifest.write( "# This file is used to define which dotfiles you want tracked with updot.py\n" )
    manifest.write( "# Add the path to each dotfile you wish to track below this line\n" )
    manifest.close();
    try:
        print "Getting default text editor..."
        editor = os.environ.get('EDITOR')
        if editor == None:
            print "$EDITOR environment variable not set. Defaulting to Vim for editing."
            editor = "vim"
        print "Opening manifest file in " + editor + " for editing..."
        time.sleep(1)
        check_call( [editor, manifest_dir] )
        print "File contents updated by user.  Attempting to continue..."
        time.sleep(1)
        manifest = open( manifest_dir, "r" )
    except OSError:
        print "\n" + editor + " not found. Unable to open manifest for user editing."
        print "Add to the manifest file the path of each dotfile you wish to track."
        print "Then run this script again."
        print "Exiting..."
        sys.exit();

# Change to dotfiles repo directory
os.chdir(dotfiles_dir)

# Check if dotfiles directory is a git repo
print "\nVerifying dotfiles directory is a git repository..."
try:
    check_call( ["git", "status"], stdout = outstream, stderr = errstream )
    print "Dotfiles directory is a git repo!"
except CalledProcessError:
    # Init as a local git repo
    print "Dotfiles directory does not contain a git repository."
    print "Initializing local repository..."
    call( ["git", "init"], stdout = outstream, stderr = errstream )

# Check if remote already added
print "\nChecking for remote repository..."
try:
    check_call( ["git", "fetch", "origin", "master"], stdout = outstream, stderr = errstream )
    print "Remote repository exists!"
except CalledProcessError:
    print "No remote repository found."
    print "Adding dotfiles remote..."
    # Check if repo already exists
    try:
        check_call( ["git", "remote", "add", "origin", "git@github.com:" + github_username + "/dotfiles.git"], stdout = outstream, stderr = errstream )
        check_call( ["git", "fetch", "origin", "master"], stdout = outstream, stderr = errstream )
    except CalledProcessError:
        print "Remote repository does not exist."
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

    check_path = fullpath[1:].split( "/" )
    print check_path[0]
    print os.path.expanduser( "~" )
    if check_path[0] == os.path.expanduser( "~" ):
        print "EET WERKZ!"

    if os.path.isfile(fullpath) or os.path.isdir(fullpath):
        filename_str = os.path.basename(fullpath)
        filename = dotfiles_dir + "/" + filename_str
        if os.path.isfile(filename) and os.path.isfile( fullpath ):
            # File is already in directory, and exists locally
            # Check if local is newer
            if local_time > remote_time:
                # Local is newer, mark for update
                print "Update remote - src: " + fullpath + " dest: " + filename
                update_remote[ fullpath ] = string.lstrip( filename, "." )
                updated_files += 1
                file_timestamps[ name ] = local_time
            elif remote_time > local_time:
                # Remote file is newer than local, update local file
                print "Update local - src: " + fullpath + " dest: " + filename
                check_path = fullpath[1:].split( "/" )
                print check_path[0]
                print os.path.expanduser( "~" )
                if check_path[0] == os.path.expanduser( "~" ):
                    print "EET WERKZ!"
                update_local[ filename ] = fullpath
            else:
                # File times are the same, do nothing
                no_update_files += 1
        elif os.path.isfile( fullpath ):
            # File is not in directory, but does exist locally
            print "New remote - src: " + fullpath + " dest: " + filename
            new_remote[ fullpath ] = string.lstrip( filename, "." )
            new_files += 1
            file_timestamps[ name ] = local_time
        elif os.path.isfile( filename ):
            # File is in directory, but does not exist locally
            print "New local - src: " + fullpath + " dest: " + filename
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
    timestamps.write( str(path) + "\t" + str( time ) + "\n" )
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

    # Commit and push changes if remote files need updating
    print "\nPushing changes...\n"
    try:
        check_call(["git", "commit", "-m", "updot.py update"], stdout = outstream, stderr = errstream )
        check_call(["git", "push", "origin", "master"], stdout = outstream, stderr = errstream )
        print "Push successful!"
        print "Updated " + str( remote_file_count ) + " remote files successfully!"
        print "All remote files up to date!"
    except CalledProcessError:
        print "Error pushing changes!"
else:
    print "Nothing to push."
    print "Remote files up to date!"


local_file_count = len( update_local ) + len( new_local )
if local_file_count > 0:
    print "\nLocal files marked for update:"

    # Update all changed local files
    for src, dest in update_local.iteritems():
        filename_str = os.path.basename(src)
        call(["cp", "-v", src, dest], stdout = outstream, stderr = errstream )
        print "Updating " + filename_str + "..."

    # Add all new local files
    for src, dest in new_local.iteritems():
        filename_str = os.path.basename(src)
        call(["cp", "-v", src, dest], stdout = outstream, stderr = errstream )
        print "Copying " + filename_str + "..."

    print "\nFile copy successful!"
    print "Updated " + str( local_file_count ) + " local files successfully!"
    print "All local files up to date!"
else:
    print "\nNothing to copy."
    print "Local files up to date!"
