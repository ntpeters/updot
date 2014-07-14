# Updot - Dotfile Updater
#
# Authors:  Mike Grimes   <magrimes@mtu.edu>
#           Nate Peterson <ntpeters@mtu.edu>
#
# A script made to automatically grab all of the dotfiles a user desires to
# keep track of, and keep them synced with their github repository.
# Files to be updated should be included in a 'dotfiles.manifest' file in the
# 'dotfiles' directory that this script will create in your home directory.

from subprocess import call, check_output, check_call, CalledProcessError, STDOUT
import os
import string
import filecmp
import sys
import time
import math
import socket
import getpass
import urllib2
import shutil

# Script version
updot_version = "2.0"

# When false, unnecessary output is suppressed
debug = False

# Open output streams
devnull = open(os.devnull, "w")

# Setup silent flag for curl
silentflag = "-s"

# Set active output streams
outstream = devnull
errstream = devnull

# Set debug options
if debug:
    outstream = sys.stdout
    errstream = sys.stderr
    silentflag = ""

# Scrpt vars
github_username = ""
git_name        = ""
git_email       = ""
manifest        = None
timestamps      = None
file_timestamps = {}
files           = {}

# Setup directory variables
updot_dir     = os.path.dirname(os.path.abspath( __file__ ))
user_home_dir = os.path.expanduser( "~" )
dotfiles_dir  = user_home_dir + "/dotfiles"
backup_dir    = user_home_dir + "/.dotfiles_backup"
ssh_key_path  = user_home_dir + "/.ssh/id_rsa.pub"
manifest_path = dotfiles_dir + "/dotfiles.manifest"

def check_internet():
    # Try connecting to Google to see if there is an active internet connection
    print "\nChecking internet connection..."
    try:
        urllib2.urlopen('http://74.125.225.103/', timeout = 1)
        print "Internet connection - Okay"
    except urllib2.URLError:
        print "No internet connection detected!"
        print "Check your connection, then rerun this script."
        print "Exiting..."
        sys.exit()

def github_setup():
    global git_name
    global git_email
    global github_username

    print "\nInspecting local git configuration..."

    # Check for user name
    try:
        git_name = check_output(["git", "config", "user.name"])[:-1]
        print "gitconfig user.name - Okay"
    except CalledProcessError:
        print "\nName not found in git config."
        print "Please provide the name you would like associated with your commits (ie. Mike Grimes)"
        git_name = raw_input('Enter Name: ')
        call(["git", "config", "--global", "user.name", git_name])
        print "Name stored in git config. Welcome to git, " + git_name + "!"

    # Check for email
    try:
        git_email = check_output(["git", "config", "user.email"])[:-1]
        print "gitconfig user.email - Okay"
    except CalledProcessError:
        print "\nEmail not found in git config."
        print "Please provide the email you would like associated with your commits."
        git_email = raw_input('Enter Email: ')
        call(["git", "config", "--global", "user.email", git_email])
        print "Email stored to git config."

    # Try to get GitHub username from git config
    print "\nAttempting to retrieve GitHub username..."
    try:
        github_username = check_output(["git", "config", "github.user"])[:-1]
    except CalledProcessError:
        print "GitHub user entry does not exist in git config, creating now..."
        call(["git", "config", "--global", "github.user", ""], stdout = outstream, stderr = errstream)

    # Check if GitHub username has been set
    if len(github_username) == 0:
        print "No GitHub username found. Please provide one now."
        github_username = raw_input('Enter GitHub username: ')
        print "Storing username in git config."
        call(["git", "config", "--global", "github.user", github_username], stdout = outstream, stderr = errstream)

    print "GitHub Username: " + github_username

    print "\nTrying remote access to GitHub..."
    try:
        check_output(["ssh", "-T", "git@github.com"], stderr = STDOUT)
    except CalledProcessError as e:
        print str(e.output)[:-1]
        if "denied" in str(e.output):
            print "Public key not setup with GitHub!"
	    ssh_setup()
        else:
            print "Connected to GitHub successfully!"

def ssh_setup():
    print "\nChecking for existing local public key..."
    pub_key = None
    try:
        pub_key = open(ssh_key_path, "r")
        print "Public key found locally."
    except IOError:
        print "Public key not found locally. Generating new SSH keys..."
        print "The following prompts will guide you through creating a new key pair."
        print "(Please leave directory options set to default values)\n"
        call(["ssh-keygen", "-t", "rsa", "-C", git_email])

    print "\nAdding to SSH agent..."
    try:
        check_call(["eval", "\"$(ssh-agent -s)\""])
        check_call(["ssh-add", "~/.ssh/id_rsa"])
        print "Key added to agent successfully."
    except (CalledProcessError, OSError):
        print "Failed to add to agent (probably not an issue)"

    pub_key = open(ssh_key_path, "r")

    print "\nAdding key to GitHub..."
    hostname = socket.gethostname().split('.')[0]
    username = getpass.getuser()
    response = ""
    add_fail = False
    try:
        json = "{\"title\":\"" + username + "@" + hostname + "\", \"key\":\"" + pub_key.read()[:-2] + "\"}"
        response = check_output(["curl", silentflag, "-u", github_username, "https://api.github.com/user/keys", "-d", json])
    except CalledProcessError:
        add_fail = True

    if "Bad credentials" in response:
        add_fail = True

    if add_fail:
        print "Failed to add key to GitHub account!"
        print "Please follow the directions on the following page, then rerun this script:"
        print "https://help.github.com/articles/generating-ssh-keys"
        print "Exiting..."
        sys.exit()
    else:
        print "Key added to GitHub successfully!"

def directory_setup():
    # Check if dotfile directory exists, and create it if it doesn't
    print "\nChecking for '~/dotfiles' directory..."
    if not os.path.exists(dotfiles_dir):
        print "Dotfiles directory does not exist."
        print "Creating dotfiles directory..."
        os.makedirs(dotfiles_dir)
    else:
        print "Dotfiles directory exists!"

def manifest_setup():
    global manifest

    # Open manifest file, or create it if it doesn't exist
    print "\nChecking for 'dotfiles.manifest'..."
    try:
        manifest = open(manifest_path, "r")
        print "Manifest file exists!"
    except IOError:
        print "Manifest file not found!"
        print "Creating empty 'dotfiles.manifest'..."
        manifest = open(manifest_path, "w+")
        manifest.write("# updot.py Dotfile Manifest\n")
        manifest.write("# This file is used to define which dotfiles you want tracked with updot.py\n")
        manifest.write("# Add the path to each dotfile you wish to track below this line\n\n")
        manifest.close();
        try:
            print "Getting default text editor..."
            editor = os.environ.get('EDITOR')
            if editor == None:
                print "Default editor unknown. Defaulting to Vim for editing."
                editor = "vim"
            raw_input("Press Enter to continue editing manifest...")
            print "Opening manifest file in " + editor + " for editing..."
            time.sleep(1)
            check_call([editor, manifest_path])
            print "File contents updated by user.  Attempting to continue..."
            manifest = open(manifest_path, "r")
        except OSError:
            print "\n" + editor + " not found. Unable to open manifest for user editing."
            print "Add to the manifest file the path of each dotfile you wish to track."
            print "Then run this script again."
            print "Exiting..."
            sys.exit()

def backup_file(file_name, src_path):
    if os.path.exists(src_path):
        print "Removing " + name + " from home directory..."

        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)

        dst_path = os.path.join(backup_dir, file_name)

        shutil.move(src_path, dst_path)

def update_links():
    print "\nUpdating symlinks...\n"
    for name, path in files.iteritems():
	if len(name) > 0 and len(path) > 0:
            path = string.rstrip(path, "\n")
            src_path = os.path.expanduser(path)
	    dst_name = name
            if name[0] == ".":
                dst_name = name[1:]
            dst_path = os.path.join(dotfiles_dir, dst_name)

            if not os.path.islink(src_path) and os.path.exists(src_path) and not os.path.isfile(dst_path):
                print "Moving " + name + " to dotfiles directory..."
                shutil.move(src_path, dst_path)
                print "Linking " + name + " into home directory..."
                os.symlink(dst_path, src_path)
            elif os.path.isfile(dst_path):
                backup_file(name, src_path)
                print "Linking " + name + " into home directory..."
                os.symlink(dst_path, src_path)

def repo_setup():
    # Change to dotfiles repo directory
    os.chdir(dotfiles_dir)

    # Check if dotfiles directory is a git repo
    print "\nVerifying dotfiles directory is a git repository..."

    if os.path.exists(dotfiles_dir + "/.git"):
        print "Dotfiles directory is a git repo!"
    else:
        # Init as a local git repo
        print "Dotfiles directory does not contain a git repository."
        print "Initializing local repository..."
        call(["git", "init"], stdout = outstream, stderr = errstream)

    # Check if remote already added
    print "\nChecking for remote repository..."
    try:
        check_call(["git", "fetch", "origin", "master"], stdout = outstream, stderr = errstream)
        print "Remote repository exists!"
    except CalledProcessError:
        print "No remote repository found."
        print "Adding dotfiles remote..."
        # Check if repo already exists
        try:
            urllib2.urlopen("http://www.github.com/" + github_username + "/dotfiles")
            call(["git", "remote", "add", "origin", "git@github.com:" + github_username + "/dotfiles.git"], stdout = outstream, stderr = errstream)
        except HTTPError:
            print "Remote repository does not exist."
            print "Creating GitHub repository...\n"

            # Create repo on GitHub
            print "GitHub password required."
            call(["curl", silentflag, "-u", github_username, "https://api.github.com/user/repos", "-d", "{\"name\":\"dotfiles\", \"description\":\"My dotfiles repository\"}"], stdout = outstream)
            print "\nAdding dotfiles remote..."
            call(["git", "remote", "add", "origin", "git@github.com:" + github_username + "/dotfiles.git"], stdout = outstream, stderr = errstream)

            print "\nCreating initial commit..."
            call(["git", "add", ".", "-A"], stdout = outstream, stderr = errstream)
            call(["git", "commit", "-m", "\"Initial commit.\""], stdout = outstream, stderr = errstream)

def pull_changes():
    # Pull most recent files from remote repository for comparison
    print "\nPulling most recent revisions from remote repository..."
    call(["git", "pull", "origin", "master"], stdout = outstream, stderr = errstream)

    # Check for a readme, and create one if one doesn't exist
    if not os.path.isfile("README.md"):
        #Create Readme file
        print "\nReadme not found."
        print "Creating readme file..."
        readme = open("README.md", "w+")
        readme.write("dotfiles\n")
        readme.write("========\n")
        readme.write("My dotfiles repository.\n\n")
        readme.write("Created and maintained by the awesome 'updot.py' script!\n\n")
        readme.write("Get the script for yourself here: https://github.com/magrimes/updot\n")
        readme.close()
        call(["git", "add", dotfiles_dir + "/README.md"], stdout = outstream, stderr = errstream)

def push_changes():
    print "\nPushing updates to remote repository..."
    call(["git", "add", ".", "-A"], stdout = outstream, stderr = errstream)
    call(["git", "commit", "-m", "\"updot.py update\""], stdout = outstream, stderr = errstream)
    call(["git", "push", "origin", "master"], stdout = outstream, stderr = errstream)

def read_manifest():
    global files

    print "\nReading manifest file..."
    for path in manifest:
        # Don't process line if it is commented out
        if path[0] != "#":
            filename = path.split("/")[-1][:-1]
            files[str(filename)] = path

def main():
    print "updot v" + updot_version + " - Dotfile update script"

    check_internet()
    github_setup()
    directory_setup()
    repo_setup()
    pull_changes()
    manifest_setup()
    read_manifest()
    update_links()
    push_changes()

    print "\nComplete - Dotfiles updated!"

if __name__ == "__main__":
    main()
