#!/usr/bin/env python

# Updot - Dotfile Updater
#
# Authors:  Mike Grimes   <magrimes@mtu.edu>
#           Nate Peterson <ntpeters@mtu.edu>
#
# A script made to automatically grab all of the dotfiles a user desires to
# keep track of, and keep them synced with their GitHub repository.
# Files to be updated should be included in a 'dotfiles.manifest' file in the
# 'dotfiles' directory that this script will create in your home directory.

from __future__ import print_function
from __future__ import unicode_literals
from __future__ import absolute_import

from subprocess import call, check_call, CalledProcessError, STDOUT
from datetime import datetime
import os
import string
import filecmp
import sys
import time
import math
import socket
import getpass
import shutil
import argparse
import json
import base64

# Attempt importing check_output, this fails on Python older than 2.7
# so we need to define it ourselves
try:
    from subprocess import check_output
except:
    # Source: https://gist.github.com/edufelipe/1027906
    import subprocess
    def check_output(*popenargs, **kwargs):
        """
        Run command with arguments and return its output as a byte string.
        Backported from Python 2.7 as it's implemented as pure python on stdlib.
        """
        process = subprocess.Popen(stdout=subprocess.PIPE, *popenargs, **kwargs)
        output, unused_err = process.communicate()
        retcode = process.poll()
        if retcode:
            cmd = kwargs.get("args")
            if cmd is None:
                cmd = popenargs[0]
            error = subprocess.CalledProcessError(retcode, cmd)
            error.output = output
            raise error
        return output


# Get proper urllib for Python version
try:
    # Python 3
    import urllib.request as urllib2
except:
    # Python 2
    import urllib2

# Setup input for use in Python 2 or 3
try:
    input = raw_input
except NameError:
    pass

# Define iter funcs based on Python version
try:
    dict.iteritems
except AttributeError:
    # Python 3
    def itervalues(d):
        return iter(d.values())
    def iteritems(d):
        return iter(d.items())
else:
    # Python 2
    def itervalues(d):
        return d.itervalues()
    def iteritems(d):
        return d.iteritems()

# Script version
updot_version = "2.12"

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
commit_message  = "updot.py update"
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
    """Enable debug mode"""
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

def basic_auth(username, password):
    """
    Compose a basic auth string.

    Keyword Args:
    username -- the username to encode
    password -- the password to encode
    """
    return 'Basic %s' % base64.encodestring(('%s:%s' %  (username, password)).encode('UTF-8')).strip().decode('UTF-8')

def post_request(url, data, username):
    """
    Issue a post request to a remote host.
    Handles user authentication.
    Also handles two-factor authentication with GitHub.

    Keyword Args:
    url -- the url to post to
    data -- the payload to post to the url
    username -- the username to authenticate with the remote host
    """
    headers = { 'Content-Type' : 'application/json' }
    request = urllib2.Request(url, data, headers)

    retries = 0
    max_attempts = 1
    while retries < max_attempts:
        try:
            response = urllib2.urlopen(request)
            success = True
        except urllib2.HTTPError as error:
            if error.code == 401:
                otp_header = error.info().get('X-Github-OTP')
                dprint("X-Github-OTP: " + str(otp_header))
                if otp_header and "required" in otp_header:
                    sprint("Two-Factor Authentication enabled for your account!")
                    sprint("Please enter 2FA code to continue.")
                    auth_code = input("2FA Code: ")
                    request.add_header('X-Github-OTP', auth_code)
                    continue
                else:
                    sprint("Password Required.")
                    passwd = getpass.getpass()
                    auth = basic_auth(username, passwd)
                    dprint("Auth: " + auth)
                    request.add_header('Authorization', auth)
                    continue

            success = False

        retries += 1

    return success

def check_dependencies():
    """
    Verify script dependencies prior to execution.
    Checks for a git installation and an active internet connection.
    """
    # Check if git is installed
    sprint("\nChecking for git...")
    try:
        check_call(["git", "--version"], stdout = outstream, stderr = errstream)
        sprint("Git installation - Okay")
    except (OSError, CalledProcessError):
        sprint("Git not found!")
        sprint("Install git, then rerun this script.")
        sprint("Exiting...")
        sys.exit()

    # Ensure there is an internet connection
    sprint("\nChecking internet connection...")
    try:
        # Try connecting to Google to see if there is an active internet connection
        urllib2.urlopen('http://www.google.com/', timeout = 5)
        sprint("Internet connection - Okay")
    except urllib2.URLError:
        sprint("No internet connection detected!")
        sprint("Check your connection, then rerun this script.")
        sprint("Exiting...")
        sys.exit()

def github_setup():
    """
    Ensures that git config is setup and remote access to GitHub is successful.
    """
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
        git_name = input('Enter Name: ')
        call(["git", "config", "--global", "user.name", git_name])
        sprint("Name stored in git config. Welcome to git, " + git_name + "!")

    # Check for email
    try:
        git_email = check_output(["git", "config", "user.email"])[:-1]
        sprint("gitconfig user.email - Okay")
    except CalledProcessError:
        sprint("\nEmail not found in git config.")
        sprint("Please provide the email you would like associated with your commits.")
        git_email = input('Enter Email: ')
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
        github_username = input('Enter GitHub username: ')
        sprint("Storing username in git config.")
        call(["git", "config", "--global", "github.user", github_username], stdout = outstream, stderr = errstream)

    # Decode the username string if needed
    try:
        github_username = github_username.decode()
    except:
        pass

    sprint("GitHub Username: " + github_username)

    sprint("\nTrying remote access to GitHub...")
    try:
        check_output(["ssh", "-T", "git@github.com"], stderr = STDOUT)
    except CalledProcessError as e:
        sprint(e.output.decode()[:-1])
        if "denied" in str(e.output):
            sprint("Public key not setup with GitHub!")
            ssh_setup()
        else:
            sprint("Connected to GitHub successfully!")

def ssh_setup():
    """
    Checks for a public SSH key and creates one if none is found.
    Also attempts to add key to the ssh-agent.
    """
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
        check_call(["ssh-add", "~/.ssh/id_rsa"])
        sprint("Key added to agent successfully.")
    except (CalledProcessError, OSError):
        sprint("Failed to add to agent. Is 'ssh-agent' running?")

    pub_key = open(ssh_key_path, "r")

    sprint("\nAdding key to GitHub...")
    hostname = socket.gethostname()
    username = getpass.getuser()
    response = ""
    data_dict = { 'title' : username + "@" + hostname,
            'key'   : pub_key.read().strip()
            }
    data = json.dumps(data_dict).encode("UTF-8")
    url = "https://api.github.com/user/keys"
    post_succeeded = post_request(url, data, github_username)
    if post_succeeded:
        sprint("Key added to GitHub successfully!")
    else:
        sprint("Failed to add key to GitHub account!")
        sprint("Please follow the directions on the following page, then rerun this script:")
        sprint("https://help.github.com/articles/generating-ssh-keys")
        sprint("Exiting...")
        sys.exit()

def directory_setup():
    """Ensures that the dotfiles directory exists, and creates it otherwise."""
    # Check if dotfile directory exists, and create it if it doesn't
    sprint("\nChecking for '~/dotfiles' directory...")
    if not os.path.exists(dotfiles_dir):
        sprint("Dotfiles directory does not exist.")
        sprint("Creating dotfiles directory...")
        os.makedirs(dotfiles_dir)
    else:
        sprint("Dotfiles directory exists!")

def manifest_setup():
    """
    Ensures a manifest file exists in the dotfiles directory.
    If none is found one is created, and it is opened for editing by the user.
    Attempts to use system default editor, otherwise defaults to vi.
    """
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
                editor = "vi"
            input("Press Enter to continue editing manifest...")
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
    """
    Moves file to backup directory. This is used in place of deleting files.

    Keyword Args:
    file_name -- name of the file to backup
    src_path -- path to the file to be backed up
    """
    if os.path.exists(src_path):
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)

        # Prepend datetime to backup filename to prevent overwriting backup files
        current_datetime = datetime.now().isoformat()
        file_name = "[" + current_datetime + "]" + file_name

        dst_path = os.path.join(backup_dir, file_name)
        shutil.move(src_path, dst_path)

def update_links():
    """
    Updates all symlinks to files in the manifest, ensuring they are all valid.

    Cases Handled:
    1. A file exists in both the dotfile and target directories: It is removed
    from the target directory and linked.
    2. The file does not exist in the target directory, but does in the dotfile
    directory: It is linked.
    3. The file exists in the target directory, but not the dotfile directory:
    It is moved to the dotfile directory and linked.
    4. The file does not exist in target or dotfile directories: A warning is
    displayed.
    5. The file exists in the dotfile directory, and a link exists in the target
    directory: Nothing is done.
    6. The file does not exist in the dotfile directory, and a link exists in
    the target directory: The dead link is removed.
    """
    sprint("\nChecking symlinks...\n")
    for name, path in iteritems(files):
        if len(name) > 0 and len(path) > 0:
            path = path.strip("\n")
            src_path = os.path.expanduser(path)
            src_dir = src_path[:len(name) * -1]
            dst_name = name
            if name[0] == ".":
                dst_name = name[1:]
            dst_path = os.path.join(dotfiles_dir, dst_name)

            indent_space = " " * (longest_name - len(name))

            # Handle Possible Conditions:
            # src = target dir (from manifest); dst = dotfile dir
            # 1: src:exist  && dst:exist  => backup and link
            # 2: src:!exist && dst:exist  => link
            # 3: src:exists && dst:!exist => move and link
            # 4: src:!exist && dst:!exist => warning
            # 5: src:link   && dst:exist  => okay
            # 6: src:link   && dst:!exist => delete link

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
    """
    Ensures local and remote git repositories are set up.
    If no local repo is found, one is initialized.
    If no remote repo is found on GitHub, one is created use the GitHub API.
    """
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
        sprint("Repository has remote!")
    except CalledProcessError:
        sprint("No remote added to repository!")
        sprint("Adding dotfiles remote...")
        # Check if repo already exists
        try:
            urllib2.urlopen("http://www.github.com/" + github_username + "/dotfiles")
            call(["git", "remote", "add", "origin", "git@github.com:" + github_username + "/dotfiles.git"], stdout = outstream, stderr = errstream)
            sprint("Remote added successfully.")
        except urllib2.HTTPError:
            sprint("Remote repository does not exist.")
            sprint("Creating GitHub repository...\n")

            # Create repo on GitHub
            url = "https://api.github.com/user/repos"
            data_dict = { 'name' : 'dotfiles',
                    'description' : 'My dotfiles repository'
                    }
            data = json.dumps(data_dict).encode("UTF-8")
            post_request(url, data, github_username)

            sprint("\nAdding dotfiles remote...")
            call(["git", "remote", "add", "origin", "git@github.com:" + github_username + "/dotfiles.git"], stdout = outstream, stderr = errstream)

            sprint("\nCreating initial commit...")
            call(["git", "add", ".", "-A"], stdout = outstream, stderr = errstream)
            call(["git", "commit", "-m", "\"Initial commit.\""], stdout = outstream, stderr = errstream)

def pull_changes():
    """Check for remote changes, and pull if any are found."""
    sprint("\nChecking for remote changes...")

    # Only pull if master branch exists
    remote_branches = check_output(["git", "ls-remote", "--heads", "origin"], stderr = errstream)
    if "master" in remote_branches.decode("UTF-8"):
        try:
            # Check if we need to pull
            for i in range(2):
                try:
                    check_call(["git", "fetch", "origin", "master"], stdout = outstream, stderr = errstream)
                    status = check_output(["git", "diff", "origin/master", "HEAD", "--name-status"], stderr = errstream)
                    break
                except CalledProcessError:
                    check_call(["git", "remote", "update", "--prune"], stdout = outstream, stderr = errstream)
                    check_call(["git", "checkout", "master", "--force"], stdout = outstream, stderr = errstream)

            if status == None:
                sprint("\nUnable to pull changes: Error reaching repository.")
            elif len(status) > 0:
                sprint("\nRemote Changes:")
                parse_print_diff(status)

                sprint("\nPulling most recent revisions from remote repository...")
                check_call(["git", "pull", "origin", "master"], stdout = outstream, stderr = errstream)
            else:
                sprint("\nNo remote changes!")
        except CalledProcessError:
            sprint("\nFailed to pull changes.")
    else:
        sprint("\nNo remote master found! Not pulling.")

def push_changes():
    """Add, commit, and push all changes to the dotfiles."""
    call(["git", "add", ".", "-A"], stdout = outstream, stderr = errstream)

    status = check_output(["git", "diff", "--name-status", "--cached"], stderr = errstream)
    if len(status) > 0:
        sprint("\nLocal Changes:")
        parse_print_diff(status)
        sprint("\nPushing updates to remote repository...")
        try:
            check_call(["git", "commit", "-m", commit_message], stdout = outstream, stderr = errstream)
            check_call(["git", "push", "origin", "master"], stdout = outstream, stderr = errstream)
        except CalledProcessError:
            sprint("Error: Failed to push changes!")
    else:
        sprint("\nNo changes to push!")

def check_readme():
    """Check if a readme exists, and create a default one if not."""
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
        readme.write("Get the script for yourself here: https://github.com/ntpeters/updot\n")
        readme.close()
        call(["git", "add", dotfiles_dir + "/README.md"], stdout = outstream, stderr = errstream)


def read_manifest():
    """Read in the file paths to track from the manifest file."""
    global files
    global longest_name

    sprint("\nReading manifest file...")
    for path in manifest:
        # Don't process line if it is commented out
        if path[0] != "#":
            filename = path.split("/")[-1][:-1]
            files[str(filename)] = path
            longest_name = len(filename) if (len(filename) > longest_name) else longest_name

def parse_print_diff(diff_string):
    """
    Parses the git diff file statuses and prints them out in a more readable
    format.

    Keyword Args:
    diff_string -- git diff status string to process
    """
    file_statuses = diff_string.decode('UTF-8').split("\n")

    status_dict = {}
    longest_status = 0
    for file_status in file_statuses:
        if(len(file_status) > 0):
            code = file_status[:1]
            name = file_status[1:].strip()
            status_dict[name] = code
            longest_status = len(name) if len(name) > longest_status else longest_status

    for name, code in iteritems(status_dict):
        indent_space = (longest_status - len(name)) * " "

        line = name + indent_space + " - "
        if code == "M":
            line += "Modified"
        elif code == "A":
            line += "Added"
        elif code == "D":
            line += "Deleted"
        elif code == "R":
            line += "Renamed"
        elif code == "C":
            line += "Copied"
        elif code == "U":
            line += "Updated (Unmerged)"
        else:
            line += "Unknown Status (" + code + ")"

        sprint(line)

def get_status():
    """Display the status of local and remote dotfiles."""
    if os.path.exists(dotfiles_dir):
        os.chdir(dotfiles_dir)

        changes_found = False

        # Get local status
        try:
            # Mark all untracked files with 'intent to add'
            check_call(["git", "add", "-N", "."], stdout = outstream, stderr = errstream)
            status = check_output(["git", "diff", "--name-status"])
            status += check_output(["git", "diff", "--name-status", "--cached"])

            if len(status) > 0:
                sprint("\nLocal Dotfiles Status:")
                parse_print_diff(status)
                changes_found = True
            else:
                sprint("\nNo local changes!")
        except CalledProcessError:
            sprint("\nError: Unable to get local status")

        # Get remote status
        try:
            check_call(["git", "fetch", "origin"], stdout = outstream, stderr = errstream)
            status = check_output(["git", "diff", "origin/master", "HEAD", "--name-status"], stderr = errstream)

            if len(status) > 0:
                sprint("\nRemote Dotfiles Status:")
                parse_print_diff(status)
                changes_found = True
            else:
                sprint("\nNo remote changes!")
        except CalledProcessError:
            sprint("\nError: Unable to get remote status")

        if changes_found:
            sprint("\nChanges Detected: You should run Updot to sync changes")
    else:
        sprint("\nError: Dotfiles directory does not exist")

def main():
    global silent
    global sprint
    global dprint
    global commit_message

    # Parse command line arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--debug", help="Print debug output during execution", action="store_true")
    parser.add_argument("-s", "--silent", help="Print nothing during execution", action="store_true")
    parser.add_argument("-m", "--message", help="Add a custom message to this commit")
    parser.add_argument("--status", help="Print the current status of the dotfiles directory", action="store_true")
    args = parser.parse_args()

    # Set options based on args
    if args.silent:
        silent = True
    elif args.debug:
        set_debug()

    # Set custom commit message if one was provided
    if args.message:
        commit_message = args.message

    # Setup custom print functions
    sprint = print if not silent else lambda *a, **k: None
    dprint = print if debug else lambda *a, **k: None

    sprint("updot v" + updot_version + " - Dotfile update script")
    if debug:
        sprint("Debug Mode: Enabled")

    # Print the dotfile dir status and exit
    if args.status:
        get_status()
        exit()

    # Execute script
    check_dependencies()
    github_setup()
    directory_setup()
    repo_setup()
    pull_changes()
    check_readme()
    manifest_setup()
    read_manifest()
    update_links()
    push_changes()

    sprint("\nComplete - Dotfiles updated!")

if __name__ == "__main__":
    main()
