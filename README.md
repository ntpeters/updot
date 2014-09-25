#updot
Updot is a dotfile update script that keeps your dotfiles in sync between
computers via GitHub.

This script moves the specified dotfiles to `~/dotfiles`, and then symlinks
them back into their original locations.

Dotfiles are not deleted when they are removed from the home directory, they
are instead backed up to `~/.dotfiles_backup`

##Installation
You can grab the scrip with the following call:
```
curl https://raw.githubusercontent.com/magrimes/updot/master/updot.py -o
.updot/updot.py --create-dirs
```

For ease of use I would also recommend adding the following alias to your
shell config:
```
alias updot='python ~/.updot/updot.py'
```

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
`updot.py update`. This can be overridden when running the scrip with the `-m`
or `--message` flags.  The message supplied will then be used as the commit
message for the current update.
```
python updot.py -m "Add custom commit message"
python updot.py --message "Add another custom commit message"
```

###Status
If you simply wish to see the status of the local and remote dotfiles
repositories, just run the scipt with the `--status` flag.
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
This script should run fine in either Python 2 or Python 3.
Tested Python 2 version: 2.7.4
Tested Python 3 version: 3.3.1
