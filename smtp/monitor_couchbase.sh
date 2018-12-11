#!/bin/sh

# SUBJECT=$(/sbin/ifconfig | grep -Eo 'inet (addr:)?([0-9]*\.){3}[0-9]*' | grep -Eo '([0-9]*\.){3}[0-9]*' | grep -v '127.0.0.1' | head -1)
SUBJECT="couchbase"
TO="couchbase@rackspace.com"
FROM="couchbase@rackspace.com"
MINUTES=5
CHECK=false
LOGWATCH=false
BACKUP=false
DIR="/var/log/couchbase"

# validate integer
function is_int() {
    return $(test "$@" -eq "$@" > /dev/null 2>&1); 
}

# show usage
function show_usage() {
    echo "usage $(basename $0) [-t <to>] [-f <from>] [-s <subject>] [-m <minutes>] [-c check] [-l logwatch] [-b backup] [-d directory] FILE";
    echo "run and look for critical, unsuccessful, or true in couchbase monitor script outputs, then send email with output if found"
    echo "-h help"
    echo "-t send email to"
    echo "-f send email from"
    echo "-s send email subject"
    echo "-m last modified time in minutes ago of script output"
    echo "-c run check_couchbase.py"
    echo "-l run logwatch_couchbase.py"
    echo "-b run backup_couchbase.py"
    echo "-d directory to search for FILE"
    echo "FILE name of file to search"
    exit 0; 
}

function grep_file() {
    RPT=$(find $DIR -type f -mmin -$MINUTES -name $1)
    COUNT=$(grep -i 'critical\|unsuccessful\|true' ${RPT} | wc -l)
    echo "grep -i 'critical\|unsuccessful\|true' $RPT | wc -l: $COUNT"
    
    if [ $COUNT -gt 0 ]
    then
        mailx -s $SUBJECT -r $FROM $TO < $RPT
    fi
}

# parse options
while getopts ":t:f:s:m:d:clb" OPT; do
    case $OPT in
        t)
            TO=$OPTARG
            ;;

        f)
            FROM=$OPTARG
            ;;

        s)
            SUBJECT=$OPTARG
            ;;

        m)
            if is_int $OPTARG;
                then
                   MINUTES=$OPTARG
                else
                   show_usage
            fi
            ;;

        c)
            CHECK=true
            ;;

        l)
            LOGWATCH=true
            ;;

        b)
            BACKUP=true
            ;;

        d)
            DIR=${OPTARG%/}
            ;;

        *)
            #Show script usage
            show_usage
            ;;
    esac
done

# done parsing options, move to next value
shift $((OPTIND-1))

# if no fixed args are passed, show usage
if [ -z "$1" ]; then
    show_usage;
else 
    VAR1="$1";
fi

if [ $CHECK == 'true' ]
then
    echo "/opt/couchbase/scripts/check_couchbase.py --config /opt/couchbase/scripts/check_couchbase.yaml"
    /opt/couchbase/scripts/check_couchbase.py --config /opt/couchbase/scripts/check_couchbase.yaml
    grep_file $VAR1
    exit 0
fi

if [ $LOGWATCH == 'true' ]
then
    echo "/opt/couchbase/scripts/logwatch_couchbase.py --config /opt/couchbase/scripts/logwatch_couchbase.yaml"
    /opt/couchbase/scripts/logwatch_couchbase.py --config /opt/couchbase/scripts/logwatch_couchbase.yaml
    grep_file $VAR1
    exit 0
fi

if [ $BACKUP == 'true' ]
then
    echo "/opt/couchbase/scripts/backup_couchbase.py --config /opt/couchbase/scripts/backup_couchbase.yaml"
    /opt/couchbase/scripts/backup_couchbase.py --config /opt/couchbase/scripts/backup_couchbase.yaml
    grep_file $VAR1
    exit 0
fi
