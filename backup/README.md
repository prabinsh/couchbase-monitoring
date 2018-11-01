# Couchbase Plugin
A plugin to manage Couchbase backups. This will backup, compact and merge backups.  

## Requirements
* Python requests module
* PyYAML

## Configuration
Updateing the YAML config file will override default arg values.

### Minimum configuration
Make sure the following properties match your environment:
* cluster
* username
* password
* cbbackupmgr

### Format
Default service descriptions are built in the following format:
"{host}:{action}:{status}"

### Couchbase Alerts
This plugin comes pre-configured to backup and compact, but not merge unless the schedule is set.
It will be necessary to update the variables to reflect your Couchbase
environment. Updating variables in config file will override defaults. 

## Usage
``` 
usage: backup_couchbase.py [-h] [--archive ARCHIVE]
                           [--cbbackupmgr CBBACKUPMGR] [--config CONFIG]
                           [--cluster CLUSTER] [--create] [--dump]
                           [--file FILE] [--format FORMAT] [--keep KEEP]
                           [--purge] [--password PASSWORD] [--repo REPO]
                           [--schedule {Sunday,Monday,Tuesday,Wednesday,Thursday,Friday,Saturday}]
                           [--threads THREADS] [--username USERNAME]
                           [--verbose]

optional arguments:
  -h, --help            show this help message and exit
  --archive ARCHIVE     The archive directory used to store backup data
                        (default: /opt/couchbase/var/lib/couchbase/backups)
  --cbbackupmgr CBBACKUPMGR
                        The backup manager executable (default:
                        /opt/couchbase/bin/cbbackupmgr)
  --config CONFIG       The path to YAML config file, reading config file
                        overrides args default values (default: None)
  --cluster CLUSTER     The hostname of the Couchbase cluster (default:
                        localhost)
  --create              Create archvie and repo if they don't exist (default:
                        False)
  --dump                Dump the configuration values (default: False)
  --file FILE           The file to write results to (default: None)
  --format FORMAT       The format in which to print results. The str of
                        str.format() (default: {host}:{action}:{status})
  --keep KEEP           The number of backups to keep (default: 3)
  --purge               If the last backup failed before it finished then
                        delete the last backup and backup from the last
                        successful backup (default: False)
  --password PASSWORD   The password of the Couchbase cluster (default:
                        secret)
  --repo REPO           The name of the backup repository to backup data to
                        (default: local)
  --schedule {Sunday,Monday,Tuesday,Wednesday,Thursday,Friday,Saturday}
                        The day(s) of the week to perform merge operation,
                        option may be called multiple times. i.e. --merge
                        Sunday --merge Monday (default: [])
  --threads THREADS     The amount of parallelism to use (default: 1)
  --username USERNAME   The username of the Couchbase cluster (default:
                        readonly)
  --verbose             Enable debugging logging (default: False)

```
