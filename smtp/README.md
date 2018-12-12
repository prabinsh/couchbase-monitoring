# Couchbase Plugin
A plugin to monitor Couchbase script outputs. Runs job and then filters through outputs for errors.  

## Requirements
* sh

### Minimum configuration
Make sure the following properties match your environment:
* FILE

### Format
Default search descriptions that indicate something went wrong:
"critical|unsuccessful|true" 

## Usage
``` 
usage monitor_couchbase.sh [-t <to>] [-f <from>] [-s <severity>] [-m <minutes>] [-n <hostname>] [-i <ip addr>] [-c check] [-l logwatch] [-b backup] [-d <directory>] FILE
run and look for critical, unsuccessful, or true in couchbase monitor script outputs, then send email with output if found
-h help
-t send email to
-f send email from
-s send email severity
-m last modified time in minutes ago of script output
-n host name
-i host ip
-c run check_couchbase.py
-l run logwatch_couchbase.py
-b run backup_couchbase.py
-d directory to search for FILE
FILE name of file to search

```
