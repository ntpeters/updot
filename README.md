#updot
Updot is a dotfile update script that keeps your dotfiles in sync between
computers via GitHub.

This script moves the specified dotfiles to `~/dotfiles`, and then symlinks
them back into their original locations.

Dotfiles are not deleted when they are removed from the home directory, they
are instead backed up to `~/.dotfiles_backup`

##Installation
You can grab the script with the following call:
```
curl https://raw.githubusercontent.com/magrimes/updot/master/updot.py -o .updot/updot.py --create-dirs
```

For ease of use I would also recommend adding the following alias to your
shell config:
```
alias updot='python ~/.updot/updot.py'
```

If you are attempting to use this with a version of Python less than 2.7, you
will also need to install `argparse` manually.
This can be done via `easy_install` or `pip`:
```
easy_install argparse
pip install argparse
```

If you don't have `easy_install` or `pip`, check out these links:

https://pypi.python.org/pypi/setuptools

http://pip.readthedocs.org/en/latest/installing.html

##Usage
Just run `updot.py`, and the rest should be handled for you.

The script will ensure that your `gitconfig` settings are correct, that you
have an ssh key set up with GitHub, and will configure the local and remote
repository for you.

The dotfiles you want tracked should be added to the `dotfiles.manifest` file
located in the `~/dotfiles` directory. This will ensure that these files are
linked properly and exist in your `~/dotfiles` directory on each computer.
Any additional files kept in the `~/dotfiles` directory (even if not listed in
the manifest) will be synced with the repository automatically.

###Custom Commit Messages
By default when the script is run, any updates will have the commit message
`updot.py update`. This can be overridden when running the script with the `-m`
or `--message` flags.  The message supplied will then be used as the commit
message for the current update.
```
python updot.py -m "Add custom commit message"
python updot.py --message "Add another custom commit message"
```

###Status
If you simply wish to see the status of the local and remote dotfiles
repositories (without actually running the full script and updating), 
just run the script with the `--status` flag.
```
python updot.py --status
```

###Silent Mode
The script can also be executed in silent mode by executing with either the
`-s` or `--silent` flags. When run in this way all output will be suppressed.
```
python updot.py -s
python updot.py --silent
```

##Compatibility
This script should run fine in either Python 2 (2.6.6 & 2.7.4 tested) or 
Python 3 (3.3.1 tested).
