#!/usr/bin/env python
"""
Updot - Dotfile Updater

A script made to automatically grab all of the dotfiles a user desires to
keep track of, and keep them synced with their GitHub repository.
Files to be updated should be included in a 'dotfiles.manifest' file in the
'dotfiles' directory that this script will create in your home directory.
"""

from __future__ import print_function
from __future__ import unicode_literals
from __future__ import absolute_import

from datetime import datetime
import os
import errno
import sys
import time
import socket
import getpass
import shutil
import argparse
import json
import base64

from subprocess import call, check_call, CalledProcessError, STDOUT
try:
    # Attempt importing check_output, this fails on Python older than 2.7
    # so we need to define it ourselves
    from subprocess import check_output
except ImportError:
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
except ImportError:
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
    def itervalues(dictionary):
        """Python 3 alias for dictionary values iterator."""
        return iter(dictionary.values())
    def iteritems(dictionary):
        """Python 3 alias for dictionary items iterator."""
        return iter(dictionary.items())
else:
    # Python 2
    def itervalues(dictionary):
        """Python 2 alias for dictionary values iterator."""
        return dictionary.itervalues()
    def iteritems(dictionary):
        """Python 2 alias for dictionary items iterator."""
        return dictionary.iteritems()

try:
    base64.encodebytes
except AttributeError:
    # Python 2
    def b64encode(*args, **kwargs):
        """Python 2 alias for bas64 string encoding."""
        return base64.encodestring(*args, **kwargs)
else:
    # Python 3
    def b64encode(*args, **kwargs):
        """Python 3 alias for bas64 string encoding."""
        return base64.encodebytes(*args, **kwargs)

# Define error for handling problems detected during dotfile status checks
class DotfileStatusError(Exception):
    """
    Raised in the event of an error while checking dotfile status to prevent continued execution.
    """
    pass

# Script version
UPDOT_VERSION = "2.27"

# When false, unnecessary output is suppresed
VERBOSE = False

# When false, debug output is suppressed
DEBUG = False

# When true, no output is generated
SILENT = False

# Open output streams
devnull = open(os.devnull, "w")

# Set active output streams
outstream = devnull
errstream = devnull

# Default message used if none is provided
DEFAULT_COMMIT_MESSAGE = "updot.py update"

# Setup directory variables
UPDOT_DIR = os.path.dirname(os.path.abspath(os.path.realpath(__file__)))
USER_HOME_DIR = os.path.expanduser("~")
DOTFILES_DIR = USER_HOME_DIR + "/.dotfiles"
BACKUP_DIR = USER_HOME_DIR + "/.dotfiles_backup"
SSH_KEY_PATH = USER_HOME_DIR + "/.ssh/id_rsa.pub"
MANIFEST_PATH = DOTFILES_DIR + "/dotfiles.manifest"

# Custom print functions
def dprint(*args, **kwargs):
    """Print function alias to only print when debug flag is set."""
    if DEBUG:
        print(*args, **kwargs)

def vprint(*args, **kwargs):
    """Print function alias to only print when verbose or debug flag is set."""
    if VERBOSE or DEBUG:
        print(*args, **kwargs)

def sprint(*args, **kwargs):
    """Print function alias to only print when silent flag is not set."""
    if not SILENT:
        print(*args, **kwargs)

def set_debug():
    """Enable debug mode"""
    global DEBUG
    global VERBOSE
    global outstream
    global errstream

    DEBUG = True
    VERBOSE = True

    # Set debug options
    if DEBUG:
        outstream = sys.stdout
        errstream = sys.stderr

def basic_auth(username, password):
    """
    Compose a basic auth string.

    Keyword Args:
    username -- the username to encode
    password -- the password to encode
    """
    raw_user_pass = ('%s:%s' %  (username, password)).encode('UTF-8')
    return 'Basic %s' % b64encode(raw_user_pass).strip().decode('UTF-8')

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
    headers = {'Content-Type' : 'application/json'}
    request = urllib2.Request(url, data, headers)

    retries = 0
    max_attempts = 1
    while retries < max_attempts:
        try:
            response = urllib2.urlopen(request)
            dprint("Response:" + response.read().decode("UTF-8"))
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
    vprint("\nChecking for git...")
    try:
        check_call(["git", "--version"], stdout=outstream, stderr=errstream)
        vprint("Git installation - Okay")
    except (OSError, CalledProcessError):
        sprint("Git not found!")
        sprint("Install git, then rerun this script.")
        sprint("Exiting...")
        sys.exit()

    # Ensure there is an internet connection
    vprint("\nChecking internet connection...")
    try:
        # Try connecting to Google to see if there is an active internet connection
        urllib2.urlopen('http://www.google.com/', timeout=5)
        vprint("Internet connection - Okay")
    except urllib2.URLError:
        sprint("No internet connection detected!")
        sprint("Check your connection, then rerun this script.")
        sprint("Exiting...")
        sys.exit()

def self_update():
    """
    Checks if a newer version of updot exists in its repository, and udates
    itself if so.
    After update is complete, the script is restarted.
    """

    sprint("\nChecking for new version of updot...")

    # Check if local updot is a git repo
    os.chdir(UPDOT_DIR)
    if not os.path.exists(os.path.join(UPDOT_DIR, ".git")):
        sprint("Unable to check for new versions of updot!")
        sprint("Updot must be cloned as a git repository to be kept up to date!")
        sprint("To get the latest updates, please reinstall updot by cloning its repository.")
        return

    # Check if an update is available
    try:
        # Get remote info
        check_call(["git", "fetch"], stdout=outstream, stderr=errstream)

        # Get hashes from git to determine if an update is needed
        local = check_output(["git", "rev-parse", "@"])
        remote = check_output(["git", "rev-parse", "@{u}"])
        base = check_output(["git", "merge-base", "@", "@{u}"])

        # Check the hashes to see if we need to update
        if local != base:
            sprint("Update failed! Local changes detected to updot!")
        elif local != remote:
            sprint("New version of updot found! Updating...")
            # Update
            check_call(["git", "pull", "origin", "master"], stdout=outstream, stderr=errstream)
            sprint("Update successful. Restarting updot...\n\n")
            # Restart script
            os.execl(sys.executable, *([sys.executable]+sys.argv))
        else:
            sprint("Updot is already up to date!")
    except CalledProcessError:
        sprint("Failed to check for new version of Updot. Try again later.")

def get_github_username():
    """
    Gets the GitHub username set in the global git config.
    If the 'github.user' entry does not exist, it is created.
    """
    # Try to get GitHub username from git config
    vprint("\nAttempting to retrieve GitHub username...")
    github_username = ""
    try:
        github_username = check_output(["git", "config", "github.user"])[:-1]
    except CalledProcessError:
        sprint("GitHub user entry does not exist in git config, creating now...")
        call(["git", "config", "--global", "github.user", ""], stdout=outstream, stderr=errstream)

    # Decode the username string if needed
    github_username = github_username.decode(encoding="utf-8", errors="ignore")
    return github_username

def get_git_email():
    """Gets the email set in the global git config."""
    git_email = ""
    try:
        git_email = check_output(["git", "config", "user.email"])[:-1]
    except CalledProcessError:
        pass

    return git_email

def github_setup():
    """
    Ensures that git config is setup and remote access to GitHub is successful.
    """
    setup_okay = True

    vprint("\nInspecting local git configuration...")

    # Check for user name
    try:
        check_call(["git", "config", "user.name"])
        vprint("gitconfig user.name - Okay")
    except CalledProcessError:
        setup_okay = False
        sprint("\nName not found in git config.")
        sprint("Please provide the name you would like associated with your commits (ie. Mike Grimes)")
        git_name = input('Enter Name: ')
        call(["git", "config", "--global", "user.name", git_name])
        sprint("Name stored in git config. Welcome to git, " + git_name + "!")

    # Check for email
    git_email = get_git_email()
    if git_email:
        vprint("gitconfig user.email - Okay")
    else:
        setup_okay = False
        sprint("\nEmail not found in git config.")
        sprint("Please provide the email you would like associated with your commits.")
        git_email = input('Enter Email: ')
        call(["git", "config", "--global", "user.email", git_email])
        sprint("Email stored to git config.")

    # Check if GitHub username has been set
    github_username = get_github_username()
    if not github_username:
        setup_okay = False
        sprint("No GitHub username found. Please provide one now.")
        github_username = input('Enter GitHub username: ')
        sprint("Storing username in git config.")
        call(["git", "config", "--global", "github.user", github_username], stdout=outstream, stderr=errstream)

    vprint("GitHub Username: " + github_username)

    vprint("\nTrying remote access to GitHub...")
    try:
        check_output(["ssh", "-T", "git@github.com"], stderr=STDOUT, shell=True)
    except CalledProcessError as error:
        vprint(error.output.decode()[:-1])
        if "denied" in str(error.output):
            setup_okay = False
            sprint("Public key not setup with GitHub!")
            ssh_setup()
        else:
            vprint("Connected to GitHub successfully!")

    return setup_okay

def ssh_setup():
    """
    Checks for a public SSH key and creates one if none is found.
    Also attempts to add key to the ssh-agent.
    """
    vprint("\nChecking for existing local public key...")
    pub_key = None
    try:
        pub_key = open(SSH_KEY_PATH, "r")
        vprint("Public key found locally.")
    except IOError:
        sprint("Public key not found locally. Generating new SSH keys...")
        git_email = get_git_email()
        if not git_email:
            sprint("No email defined in global git config. Unable to generate SSH key.")
            sprint("Add email to git config and rerun this script.")

        sprint("The following prompts will guide you through creating a new key pair.")
        sprint("(Please leave directory options set to default values)\n")
        call(["ssh-keygen", "-t", "rsa", "-C", git_email.decode("UTF-8")], shell=True)

    vprint("\nAdding to SSH agent...")
    try:
        check_call(["ssh-add", "~/.ssh/id_rsa"], shell=True)
        vprint("Key added to agent successfully.")
    except (CalledProcessError, OSError):
        vprint("Failed to add to agent. Is 'ssh-agent' running?")

    pub_key = open(SSH_KEY_PATH, "r")
    sprint("\nAdding key to GitHub...")
    hostname = socket.gethostname()
    username = getpass.getuser()
    data_dict = dict([('title', username + "@" + hostname), ('key', pub_key.read().strip())])
    data = json.dumps(data_dict).encode("UTF-8")
    url = "https://api.github.com/user/keys"
    github_username = get_github_username()
    post_succeeded = post_request(url, data, github_username)
    if post_succeeded:
        vprint("Key added to GitHub successfully!")
    else:
        sprint("Failed to add key to GitHub account!")
        sprint("Please follow the directions on the following page, then rerun this script:")
        sprint("https://help.github.com/articles/generating-ssh-keys")
        sprint("Exiting...")
        sys.exit()

def directory_setup():
    """Ensures that the dotfiles directory exists, and creates it otherwise."""
    # Check if dotfile directory exists, and create it if it doesn't
    vprint("\nChecking for '~/.dotfiles' directory...")
    if not os.path.exists(DOTFILES_DIR):
        vprint("Dotfiles directory does not exist.")
        vprint("Creating dotfiles directory...")
        os.makedirs(DOTFILES_DIR)
    else:
        vprint("Dotfiles directory exists!")

def manifest_setup():
    """
    Ensures a manifest file exists in the dotfiles directory.
    If none is found one is created, and it is opened for editing by the user.
    Attempts to use system default editor, otherwise defaults to vi.
    """

    # Open manifest file, or create it if it doesn't exist
    vprint("\nChecking for 'dotfiles.manifest'...")
    try:
        manifest = open(MANIFEST_PATH, "r")
        vprint("Manifest file exists!")
    except IOError:
        sprint("Manifest file not found!")
        sprint("Creating empty 'dotfiles.manifest'...")
        manifest = open(MANIFEST_PATH, "w+")
        manifest.write("# updot.py Dotfile Manifest\n")
        manifest.write("# This file is used to define which dotfiles you want\n")
        manifest.write("# tracked with updot.py\n")
        manifest.write("# Add the path to each dotfile (relative to your home\n")
        manifest.write("# directory) you wish to track below this line\n\n")
        manifest.close()
        try:
            vprint("Getting default text editor...")
            editor = os.environ.get('EDITOR')
            if editor is None:
                vprint("Default editor unknown. Defaulting to Vim for editing.")
                editor = "vi"
            input("Press Enter to continue editing manifest...")
            sprint("Opening manifest file in " + editor + " for editing...")
            time.sleep(1)
            check_call([editor, MANIFEST_PATH])
            sprint("File contents updated by user.  Attempting to continue...")
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
        if not os.path.exists(BACKUP_DIR):
            os.makedirs(BACKUP_DIR)

        # Prepend datetime to backup filename to prevent overwriting backup files
        current_datetime = datetime.now().strftime("%Y-%m-%dT%H_%M_%S")
        file_name = "[" + current_datetime + "]" + file_name

        dst_path = os.path.join(BACKUP_DIR, file_name)
        shutil.move(src_path, dst_path)

def update_links(files):
    """
    Updates all symlinks to files in the manifest, ensuring they are all valid.

    Keyword Args:
    files -- paths to files to verify and/or update symlinks for
    """
    longest_name = 0

    sprint("\nChecking symlinks...\n")
    for path in files:
        name = path.split("/")[-1][:-1]
        longest_name = len(name) if (len(name) > longest_name) else longest_name

        if name and path:
            path = path.strip("\n")
            src_dir = path[:len(name) * -1]

            dst_dir = src_dir
            src_dir = os.path.join(USER_HOME_DIR, src_dir)
            if dst_dir and dst_dir[0] == ".":
                dst_dir = dst_dir[1:]

            update_link(src_dir, dst_dir, name, longest_name)

def update_link(src_dir, dst_dir, name, output_indent=0):
    """
    Updates the symlink between the provided source and destination paths.

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

    Keyword Args:
    src_dir -- source directory to link from
    dst_dir -- destination directory to link to
    name -- name of the file to link
    output_indent -- optional amount of spacing to indent output from this function
    """

    # Handle Possible Conditions:
    # src = target dir (from manifest); dst = dotfile dir
    # 1: src:exist  && dst:exist  => backup and link
    # 2: src:!exist && dst:exist  => link
    # 3: src:exists && dst:!exist => move and link
    # 4: src:!exist && dst:!exist => warning
    # 5: src:link   && dst:exist  => okay
    # 6: src:link   && dst:!exist => delete link

    indent_space = " " * (output_indent - len(name))
    indent_name = name + indent_space
    indent_name_space = " " * len(name) + indent_space

    dst_name = name
    if dst_name[0] == ".":
        dst_name = dst_name[1:]

    src_path = os.path.join(src_dir, name)
    dst_path = os.path.join(DOTFILES_DIR, dst_dir, dst_name)

    if os.path.exists(dst_path):
        if os.path.lexists(src_path):
            if not os.path.islink(src_path):
                #1: src:exist dst:exist => backup and link
                sprint(indent_name + " - Removing from target directory: " + src_dir)
                backup_file(name, src_path)
                sprint(indent_name_space + " - Linking into target directory: " + src_dir)
                os.symlink(dst_path, src_path)
            else:
                #5: src:link dst:exit => okay
                sprint(name + indent_space + " - Okay")
        else:
            #2: src:!exist dst:exist => link
            sprint(indent_name + " - Linking into target directory: " + src_dir)
            if not os.path.exists(src_dir):
                os.makedirs(src_dir)
            os.symlink(dst_path, src_path)
    else:
        if os.path.lexists(src_path):
            if os.path.islink(src_path):
                #6: src:link dst:!exist => delete link
                sprint(indent_name + " - Removing dead link from target directory: " + src_dir)
                os.remove(src_path)
            else:
                #3: src:exist dst:!exist => move and link
                sprint(indent_name + " - Moving to dotfiles directory...")
                try:
                    os.makedirs(os.path.dirname(dst_path))
                except OSError as error:
                    if error.errno != errno.EEXIST:
                        raise
                shutil.move(src_path, dst_path)
                sprint(indent_name_space + " - Linking into target directory: " + src_dir)
                os.symlink(dst_path, src_path)
        else:
            #4: src:!exist dst:!exist => warning
            sprint(indent_name + " - Warning: present in manifest, but no remote or local copy exists!")

def repo_setup():
    """
    Ensures local and remote git repositories are set up.
    If no local repo is found, one is initialized.
    If no remote repo is found on GitHub, one is created use the GitHub API.
    """
    # Change to dotfiles repo directory
    os.chdir(DOTFILES_DIR)

    # Check if dotfiles directory is a git repo
    vprint("\nVerifying dotfiles directory is a git repository...")

    if os.path.exists(DOTFILES_DIR + "/.git"):
        vprint("Dotfiles directory is a git repo!")
    else:
        # Init as a local git repo
        vprint("Dotfiles directory does not contain a git repository.")
        vprint("Initializing local repository...")
        call(["git", "init"], stdout=outstream, stderr=errstream)

    # Check if remote already added
    vprint("\nChecking for remote repository...")
    try:
        check_call(["git", "fetch", "origin", "master"], stdout=outstream, stderr=errstream)
        vprint("Repository has remote!")
    except CalledProcessError:
        vprint("No remote added to repository!")
        vprint("Adding dotfiles remote...")

        # Check if repo already exists
        github_username = get_github_username()
        remote_path = "git@github.com:" + github_username + "/dotfiles.git"
        try:
            urllib2.urlopen("http://www.github.com/" + github_username + "/dotfiles")
            call(["git", "remote", "add", "origin", remote_path], stdout=outstream, stderr=errstream)
            vprint("Remote added successfully.")
        except urllib2.HTTPError:
            sprint("Remote repository does not exist.")
            sprint("Creating GitHub repository...\n")

            # Create repo on GitHub
            url = "https://api.github.com/user/repos"
            data_dict = {'name': 'dotfiles', 'description': 'My dotfiles repository'}
            data = json.dumps(data_dict).encode("UTF-8")
            post_request(url, data, github_username)

            sprint("\nAdding dotfiles remote...")
            call(["git", "remote", "add", "origin", remote_path], stdout=outstream, stderr=errstream)

            sprint("\nCreating initial commit...")
            call(["git", "add", ".", "-A"], stdout=outstream, stderr=errstream)
            call(["git", "commit", "-m", "\"Initial commit.\""], stdout=outstream, stderr=errstream)

def get_repo_status(retry=True):
    """
    Get the current status of tracked dotfiles.

    Keyword Args:
    retry -- optional flag to specify if the status check should be retried on failure
    """
    try:
        check_call(["git", "fetch", "origin", "master"], stdout=outstream, stderr=errstream)
        return check_output(["git", "diff", "origin/master", "HEAD", "--name-status"], stderr=errstream)
    except CalledProcessError:
        if retry:
            check_call(["git", "remote", "update", "--prune"], stdout=outstream, stderr=errstream)
            check_call(["git", "checkout", "master", "--force"], stdout=outstream, stderr=errstream)
            return get_repo_status(False)

    return None

def pull_changes():
    """Check for remote changes, and pull if any are found."""
    sprint("\nChecking for remote changes...")

    # Only pull if master branch exists
    remote_branches = check_output(["git", "ls-remote", "--heads", "origin"], stderr=errstream)
    if "master" in remote_branches.decode("UTF-8"):
        try:
            # Check if we need to pull
            status = get_repo_status()
            if status is None:
                sprint("\nUnable to pull changes: Error reaching repository.")
            elif status:
                sprint("\nRemote Changes:")
                parse_print_diff(status)

                sprint("\nPulling most recent revisions from remote repository...")
                check_call(["git", "pull", "origin", "master"], stdout=outstream, stderr=errstream)
            else:
                sprint("\nNo remote changes!")
        except CalledProcessError:
            sprint("\nFailed to pull changes.")
    else:
        sprint("\nNo remote master found! Not pulling.")

def push_changes(commit_message):
    """
    Add, commit, and push all changes to the dotfiles.

    Keyword Args:
    commit_message -- message to use as the commit message for this update
    """
    call(["git", "add", ".", "-A"], stdout=outstream, stderr=errstream)

    status = check_output(["git", "diff", "--name-status", "--cached"], stderr=errstream)
    if status:
        sprint("\nLocal Changes:")
        parse_print_diff(status)
        sprint("\nPushing updates to remote repository...")
        try:
            check_call(["git", "commit", "-m", commit_message], stdout=outstream, stderr=errstream)
            check_call(["git", "push", "origin", "master"], stdout=outstream, stderr=errstream)
        except CalledProcessError:
            sprint("Error: Failed to push changes!")
    else:
        sprint("\nNo changes to push!")

def check_readme():
    """Check if a readme exists, and create a default one if not."""
    # Check for a readme, and create one if one doesn't exist
    if not os.path.isfile("README.md"):
        #Create Readme file
        vprint("\nReadme not found.")
        vprint("Creating readme file...")
        readme = open("README.md", "w+")
        readme.write("dotfiles\n")
        readme.write("========\n")
        readme.write("My dotfiles repository.\n\n")
        readme.write("Created and maintained by the awesome 'updot.py' script!\n\n")
        readme.write("Get the script for yourself here: https://github.com/ntpeters/updot\n")
        readme.close()
        call(["git", "add", DOTFILES_DIR + "/README.md"], stdout=outstream, stderr=errstream)


def read_manifest():
    """Read in the file paths to track from the manifest file."""
    files = []

    vprint("\nReading manifest file...")
    manifest = open(MANIFEST_PATH, "r")
    for path in manifest:
        # Don't process line if it is commented out
        if path[0] != "#":
            files.append(path)

    return files

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
        if file_status:
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

    # Track if any errors occur
    error_detected = False
    # Track if changes were detected
    changes_found = False

    # Ensure the dotfiles directory exist
    if os.path.exists(DOTFILES_DIR):
        os.chdir(DOTFILES_DIR)

        # Get local status
        try:
            # Mark all untracked files with 'intent to add'
            check_call(["git", "add", "-N", "."], stdout=outstream, stderr=errstream)
            status = check_output(["git", "diff", "--name-status"])
            status += check_output(["git", "diff", "--name-status", "--cached"])

            if status:
                sprint("\nLocal Dotfiles Status:")
                parse_print_diff(status)
                changes_found = True
            else:
                sprint("\nNo local changes!")
        except CalledProcessError:
            error_detected = True
            sprint("\nError: Unable to get local status")

        # Get remote status
        try:
            check_call(["git", "fetch", "origin"], stdout=outstream, stderr=errstream)
            status = check_output(["git", "diff", "origin/master", "HEAD", "--name-status"], stderr=errstream)

            if status:
                sprint("\nRemote Dotfiles Status:")
                parse_print_diff(status)
                changes_found = True
            else:
                sprint("\nNo remote changes!")
        except CalledProcessError:
            error_detected = True
            sprint("\nError: Unable to get remote status")
    else:
        sprint("\nWarning: Dotfiles directory does not exist. Skipping status check.")
        changes_found = True

    if error_detected:
        raise DotfileStatusError

    return changes_found

def main():
    """Script entry point."""
    global SILENT
    global VERBOSE

    # Parse command line arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--debug", help="Print debug output during execution (implies verbose)", action="store_true")
    parser.add_argument("-v", "--verbose", help="Print additional output during execution", action="store_true")
    parser.add_argument("-s", "--silent", help="Print nothing during execution", action="store_true")
    parser.add_argument("-m", "--message", help="Add a custom message to this commit")
    parser.add_argument("--status", help="Print the current status of the dotfiles directory", action="store_true")
    parser.add_argument("--selfupdate", help="Check if an update to Updot is available", action="store_true")
    parser.add_argument("--doctor", help="Ensure all dependencies are met, and git and SSH are properly configured", action="store_true")
    parser.add_argument("--relink", help="Re-link all dotfiles into place", action="store_true")
    args = parser.parse_args()

    # Set options based on args
    if args.debug:
        set_debug()
    elif args.verbose:
        VERBOSE = True
    elif args.silent:
        SILENT = True

    # Set custom commit message if one was provided
    commit_message = DEFAULT_COMMIT_MESSAGE
    if args.message:
        commit_message = args.message

    sprint("updot v" + UPDOT_VERSION + " - Dotfile update script")
    if DEBUG:
        sprint("Debug Mode: Enabled")

    if args.selfupdate:
        check_dependencies()
        self_update()
        exit()

    if args.doctor:
        check_dependencies()
        setup_check = github_setup()
        if setup_check:
            sprint("\nNo problems detected. All systems go!")
        exit()

    if args.relink:
        files = read_manifest()
        update_links(files)
        exit()

    try:
        # Check dotfile status
        changes = get_status()

        # Simply exit if user is only checking status
        if args.status:
            if changes:
                sprint("\nChanges Detected: You should run Updot to sync changes")
            exit()

        # Exit if no changes were found
        if not changes:
            sprint("No changes detected. Nothing to sync.")
            exit()

        # Prompt the user to continue if not running in silent mode
        if not SILENT:
            choice = input("\nContinue syncing detected changes? [y/n] ").lower()
            if choice == "y":
                pass
            else:
                exit()
    except DotfileStatusError:
        # Do not continue if any errors occurred during status check
        exit()

    # Execute script
    check_dependencies()
    self_update()
    github_setup()
    directory_setup()
    repo_setup()
    pull_changes()
    check_readme()
    manifest_setup()
    files = read_manifest()
    update_links(files)
    push_changes(commit_message)

    sprint("\nComplete - Dotfiles updated!")

if __name__ == "__main__":
    main()
