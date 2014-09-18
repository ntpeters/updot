# Updot - Dotfile Updater
#
# Authors:  Mike Grimes   <magrimes@mtu.edu>
#           Nate Peterson <ntpeters@mtu.edu>
#
# A script made to automatically grab all of the dotfiles a user desires to
# keep track of, and keep them synced with their GitHub repository.
# Files to be updated should be included in a 'dotfiles.manifest' file in the
# 'dotfiles' directory that this script will create in your home directory.

# Import Python3's print function in Python2
#try:
from __future__ import print_function
#except:
    #None

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
import argparse

# Script version
updot_version = "2.0"

# When false, unnecessary output is suppressed
debug = False

# When true, no output is generated
silent = False

# Custom print functions
sprint = None
dprint = None

# Open output streams
devnull = open(os.devnull, "w")

# Setup silent flag for curl
silentflag = "-s"

# Set active output streams
outstream = devnull
errstream = devnull

# Script vars
github_username = ""
git_name        = ""
git_email       = ""
manifest        = None
timestamps      = None
file_timestamps = {}
files           = {}
longest_name    = 0

# Setup directory variables
updot_dir     = os.path.dirname(os.path.abspath( __file__ ))
user_home_dir = os.path.expanduser( "~" )
dotfiles_dir  = user_home_dir + "/dotfiles"
backup_dir    = user_home_dir + "/.dotfiles_backup"
ssh_key_path  = user_home_dir + "/.ssh/id_rsa.pub"
manifest_path = dotfiles_dir + "/dotfiles.manifest"

def set_debug():
    global debug
    global outstream
    global errstream
    global silentflag

    debug = True

    # Set debug options
    if debug:
        outstream = sys.stdout
        errstream = sys.stderr
        silentflag = ""

def check_internet():
    # Try connecting to Google to see if there is an active internet connection
    sprint("\nChecking internet connection...")
    try:
        urllib2.urlopen('http://74.125.225.103/', timeout = 1)
        sprint("Internet connection - Okay")
    except urllib2.URLError:
        sprint("No internet connection detected!")
        sprint("Check your connection, then rerun this script.")
        sprint("Exiting...")
        sys.exit()

def github_setup():
    global git_name
    global git_email
    global github_username

    sprint("\nInspecting local git configuration...")

    # Check for user name
    try:
        git_name = check_output(["git", "config", "user.name"])[:-1]
        sprint("gitconfig user.name - Okay")
    except CalledProcessError:
        sprint("\nName not found in git config.")
        sprint("Please provide the name you would like associated with your commits (ie. Mike Grimes)")
        git_name = raw_input('Enter Name: ')
        call(["git", "config", "--global", "user.name", git_name])
        sprint("Name stored in git config. Welcome to git, " + git_name + "!")

    # Check for email
    try:
        git_email = check_output(["git", "config", "user.email"])[:-1]
        sprint("gitconfig user.email - Okay")
    except CalledProcessError:
        sprint("\nEmail not found in git config.")
        sprint("Please provide the email you would like associated with your commits.")
        git_email = raw_input('Enter Email: ')
        call(["git", "config", "--global", "user.email", git_email])
        sprint("Email stored to git config.")

    # Try to get GitHub username from git config
    sprint("\nAttempting to retrieve GitHub username...")
    try:
        github_username = check_output(["git", "config", "github.user"])[:-1]
    except CalledProcessError:
        sprint("GitHub user entry does not exist in git config, creating now...")
        call(["git", "config", "--global", "github.user", ""], stdout = outstream, stderr = errstream)

    # Check if GitHub username has been set
    if len(github_username) == 0:
        sprint("No GitHub username found. Please provide one now.")
        github_username = raw_input('Enter GitHub username: ')
        sprint("Storing username in git config.")
        call(["git", "config", "--global", "github.user", github_username], stdout = outstream, stderr = errstream)

    sprint("GitHub Username: " + github_username)

    sprint("\nTrying remote access to GitHub...")
    try:
        check_output(["ssh", "-T", "git@github.com"], stderr = STDOUT)
    except CalledProcessError as e:
        sprint(str(e.output)[:-1])
        if "denied" in str(e.output):
            sprint("Public key not setup with GitHub!")
            ssh_setup()
        else:
            sprint("Connected to GitHub successfully!")

def ssh_setup():
    sprint("\nChecking for existing local public key...")
    pub_key = None
    try:
        pub_key = open(ssh_key_path, "r")
        sprint("Public key found locally.")
    except IOError:
        sprint("Public key not found locally. Generating new SSH keys...")
        sprint("The following prompts will guide you through creating a new key pair.")
        sprint("(Please leave directory options set to default values)\n")
        call(["ssh-keygen", "-t", "rsa", "-C", git_email])

    sprint("\nAdding to SSH agent...")
    try:
        check_call(["eval", "\"$(ssh-agent -s)\""])
        check_call(["ssh-add", "~/.ssh/id_rsa"])
        sprint("Key added to agent successfully.")
    except (CalledProcessError, OSError):
        sprint("Failed to add to agent (probably not an issue)")

    pub_key = open(ssh_key_path, "r")

    sprint("\nAdding key to GitHub...")
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
        sprint("Failed to add key to GitHub account!")
        sprint("Please follow the directions on the following page, then rerun this script:")
        sprint("https://help.github.com/articles/generating-ssh-keys")
        sprint("Exiting...")
        sys.exit()
    else:
        sprint("Key added to GitHub successfully!")

def directory_setup():
    # Check if dotfile directory exists, and create it if it doesn't
    sprint("\nChecking for '~/dotfiles' directory...")
    if not os.path.exists(dotfiles_dir):
        sprint("Dotfiles directory does not exist.")
        sprint("Creating dotfiles directory...")
        os.makedirs(dotfiles_dir)
    else:
        sprint("Dotfiles directory exists!")

def manifest_setup():
    global manifest

    # Open manifest file, or create it if it doesn't exist
    sprint("\nChecking for 'dotfiles.manifest'...")
    try:
        manifest = open(manifest_path, "r")
        sprint("Manifest file exists!")
    except IOError:
        sprint("Manifest file not found!")
        sprint("Creating empty 'dotfiles.manifest'...")
        manifest = open(manifest_path, "w+")
        manifest.write("# updot.py Dotfile Manifest\n")
        manifest.write("# This file is used to define which dotfiles you want tracked with updot.py\n")
        manifest.write("# Add the path to each dotfile you wish to track below this line\n\n")
        manifest.close();
        try:
            sprint("Getting default text editor...")
            editor = os.environ.get('EDITOR')
            if editor == None:
                sprint("Default editor unknown. Defaulting to Vim for editing.")
                editor = "vim"
            raw_input("Press Enter to continue editing manifest...")
            sprint("Opening manifest file in " + editor + " for editing...")
            time.sleep(1)
            check_call([editor, manifest_path])
            sprint("File contents updated by user.  Attempting to continue...")
            manifest = open(manifest_path, "r")
        except OSError:
            sprint("\n" + editor + " not found. Unable to open manifest for user editing.")
            sprint("Add to the manifest file the path of each dotfile you wish to track.")
            sprint("Then run this script again.")
            sprint("Exiting...")
            sys.exit()

def backup_file(file_name, src_path):
    if os.path.exists(src_path):
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)

        dst_path = os.path.join(backup_dir, file_name)
        shutil.move(src_path, dst_path)

def update_links():
    sprint("\nChecking symlinks...\n")
    for name, path in files.iteritems():
        if len(name) > 0 and len(path) > 0:
            path = string.rstrip(path, "\n")
            src_path = os.path.expanduser(path)
            src_dir = src_path[:len(name) * -1]
            dst_name = name
            if name[0] == ".":
                dst_name = name[1:]
            dst_path = os.path.join(dotfiles_dir, dst_name)

            indent_space = " " * (longest_name - len(name))

            # TODO: Possibly clean this section up
            # Conditions:
            # src = target dir (from manifest); dst = dotfile dir
            # 1: src:exist  && dst:exist  => backup and link
            # 2: src:!exist && dst:exist  => link
            # 3: src:exists && dst:!exist => move and link
            # 4: src:!exist && dst:!exist => warning
            # 5: src:link   && dst:exist  => okay
            # 6: src:!exist && dst:link   => delete link

            if os.path.exists(dst_path):
                if os.path.lexists(src_path):
                    if not os.path.islink(src_path):
                        #1: src:exist dst:exist => backup and link
                        sprint(name + indent_space + " - Removing from target directory: " + src_dir)
                        backup_file(name, src_path)
                        sprint(" " * len(name) + indent_space + " - Linking into target directory: " + src_dir)
                        os.symlink(dst_path, src_path)
                    else:
                        #5: src:link dst:exit => okay
                        sprint(name + indent_space + " - Okay")
                else:
                    #2: src:!exist dst:exist => link
                    sprint(name + indent_space + " - Linking into target directory: " + src_dir)
                    os.symlink(dst_path, src_path)
            else:
                if os.path.lexists(src_path):
                    if os.path.islink(src_path):
                        #6: src:link dst:!exist => delete link
                        sprint(name + indent_space + " - Removing dead link from target directory: " + src_dir)
                        os.remove(src_path)
                    else:
                        #3: src:exist dst:!exist => move and link
                        sprint(name + indent_space + " - Moving to dotfiles directory...")
                        shutil.move(src_path, dst_path)
                        sprint(" " * len(name) + indent_space + " - Linking into target directory: " + src_dir)
                        os.symlink(dst_path, src_path)
                else:
                    #4: src:!exist dst:!exist => warning
                    sprint(name + indent_space + " - Warning: present in manifest, but no remote or local copy exists!")

def repo_setup():
    # Change to dotfiles repo directory
    os.chdir(dotfiles_dir)

    # Check if dotfiles directory is a git repo
    sprint("\nVerifying dotfiles directory is a git repository...")

    if os.path.exists(dotfiles_dir + "/.git"):
        sprint("Dotfiles directory is a git repo!")
    else:
        # Init as a local git repo
        sprint("Dotfiles directory does not contain a git repository.")
        sprint("Initializing local repository...")
        call(["git", "init"], stdout = outstream, stderr = errstream)

    # Check if remote already added
    sprint("\nChecking for remote repository...")
    try:
        check_call(["git", "fetch", "origin", "master"], stdout = outstream, stderr = errstream)
        sprint("Remote repository exists!")
    except CalledProcessError:
        sprint("No remote repository found.")
        sprint("Adding dotfiles remote...")
        # Check if repo already exists
        try:
            urllib2.urlopen("http://www.github.com/" + github_username + "/dotfiles")
            call(["git", "remote", "add", "origin", "git@github.com:" + github_username + "/dotfiles.git"], stdout = outstream, stderr = errstream)
        except HTTPError:
            sprint("Remote repository does not exist.")
            sprint("Creating GitHub repository...\n")

            # Create repo on GitHub
            sprint("GitHub password required.")
            call(["curl", silentflag, "-u", github_username, "https://api.github.com/user/repos", "-d", "{\"name\":\"dotfiles\", \"description\":\"My dotfiles repository\"}"], stdout = outstream)
            sprint("\nAdding dotfiles remote...")
            call(["git", "remote", "add", "origin", "git@github.com:" + github_username + "/dotfiles.git"], stdout = outstream, stderr = errstream)

            sprint("\nCreating initial commit...")
            call(["git", "add", ".", "-A"], stdout = outstream, stderr = errstream)
            call(["git", "commit", "-m", "\"Initial commit.\""], stdout = outstream, stderr = errstream)

def pull_changes():
    # Pull most recent files from remote repository for comparison
    sprint("\nPulling most recent revisions from remote repository...")
    call(["git", "pull", "origin", "master"], stdout = outstream, stderr = errstream)

    # Check for a readme, and create one if one doesn't exist
    if not os.path.isfile("README.md"):
        #Create Readme file
        sprint("\nReadme not found.")
        sprint("Creating readme file...")
        readme = open("README.md", "w+")
        readme.write("dotfiles\n")
        readme.write("========\n")
        readme.write("My dotfiles repository.\n\n")
        readme.write("Created and maintained by the awesome 'updot.py' script!\n\n")
        readme.write("Get the script for yourself here: https://github.com/magrimes/updot\n")
        readme.close()
        call(["git", "add", dotfiles_dir + "/README.md"], stdout = outstream, stderr = errstream)

def push_changes():
    sprint("\nPushing updates to remote repository...")
    call(["git", "add", ".", "-A"], stdout = outstream, stderr = errstream)
    call(["git", "commit", "-m", "\"updot.py update\""], stdout = outstream, stderr = errstream)
    call(["git", "push", "origin", "master"], stdout = outstream, stderr = errstream)

def read_manifest():
    global files
    global longest_name

    sprint("\nReading manifest file...")
    for path in manifest:
        # Don't process line if it is commented out
        if path[0] != "#":
            filename = path.split("/")[-1][:-1]
            files[str(filename)] = path
            longest_name = len(filename) if (len(filename) > longest_name) else longest_name

def main():
    global silent
    global sprint
    global dprint

    # Parse command line arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--debug", help="Print debug output during execution", action="store_true")
    parser.add_argument("-s", "--silent", help="Print nothing during execution", action="store_true")
    args = parser.parse_args()

    # Set options based on args
    if args.silent:
        silent = True
    elif args.debug:
        set_debug()

    # Setup custom print functions
    sprint = print if not silent else lambda *a, **k: None
    dprint = print if debug else lambda *a, **k: None

    sprint("updot v" + updot_version + " - Dotfile update script")
    if debug:
        sprint("Debug Mode: Enabled")

    # Execute script
    check_internet()
    github_setup()
    directory_setup()
    repo_setup()
    pull_changes()
    manifest_setup()
    read_manifest()
    update_links()
    push_changes()

    sprint("\nComplete - Dotfiles updated!")

if __name__ == "__main__":
    main()
