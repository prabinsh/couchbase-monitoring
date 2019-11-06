#!/usr/bin/env python

import argparse
import os
import logging
import logging.config
import re
import sys
import subprocess
import yaml
from datetime import datetime, timedelta

parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument("--archive",  dest="archive", action="store", default="/opt/couchbase/var/lib/couchbase/backups", help="The archive directory used to store backup data")
parser.add_argument("--cbbackupmgr",  dest="cbbackupmgr", action="store", default="/opt/couchbase/bin/cbbackupmgr", help="The backup manager executable")
parser.add_argument("--config",  dest="config", action="store", help="The path to YAML config file, reading config file overrides args default values")
parser.add_argument("--cluster",  dest="cluster", action="store", default="localhost", help="The hostname of the Couchbase cluster")
parser.add_argument("--dump",  dest="dump", action="store_true", default=False, help="Dump the configuration values")
parser.add_argument("--file",  dest="file", action="store", help="The file to write results to")
parser.add_argument("--format",  dest="format", action="store", default="{host}:{action}:{status}", help="The format in which to print results. The str of str.format()")
parser.add_argument("--keep",  dest="keep", action="store", type=int, default=3, help="The number of days to keep repository")
parser.add_argument("--purge",  dest="purge", action="store_true", default=False, help="If the last backup failed before it finished then delete the last backup and backup from the last successful backup")
parser.add_argument("--password",  dest="password", action="store", default="secret", help="The password of the Couchbase cluster")
parser.add_argument("--schedule",  dest="schedule", action="store", default="Saturday", choices=["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"], help="The day(s) of the week to perform merge operation, option may be called multiple times. i.e. --merge Sunday --merge Monday")
parser.add_argument("--threads",  dest="threads", action="store", type=int, default=1, help="The amount of parallelism to use")
parser.add_argument("--username",  dest="username", action="store", default="readonly", help="The username of the Couchbase cluster")
parser.add_argument("--verbose",  dest="verbose", action="store_true", default=False, help="Enable debugging logging")
args = parser.parse_args()

# return results of args and config file, if passed
def get_config():
    config = vars(args)
    config.update(get_logging_config())

    if config["config"]:
        try:
            with open(config["config"], 'r') as f:
                config.update(yaml.load(f))
        except IOError:
            logging.error("Unable to read config file {0}".format(args.config))
            sys.exit(1)
        except (yaml.reader.ReaderError, yaml.parser.ParserError):
            logging.error("Invalid YAML syntax in config file {0}".format(args.config))
            sys.exit(1)
        except Exception as e:
            logging.error(str(e))
            sys.exit(1)

    return config


# return initial logging configuraiton
def get_logging_config():
    config = {
        "version": 1,
        "formatters": {
            "simple": { "format": "%(asctime)s %(levelname)s %(message)s"}
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "simple",
                "stream": "ext://sys.stdout",
                "level": "DEBUG",
            }
        },
        "root": {
            "level": "INFO",
            "handlers": ["console"]
        }
    }

    return {"logging": config}


# return the name of the weekday
def weekday(number):
    wd = {
        0: "Monday",
        1: "Tuesday",
        2: "Wednesday",
        3: "Thursday",
        4: "Friday",
        5: "Saturday",
        6: "Sunday" 
    }

    return wd.get(number)


# retrive the list of backups
def get_backup_repo(config):
    logging.info("determining backup repo based on create schedule: {}".format(config["schedule"]))
    today = datetime.today()
    wd = today.weekday()

    if weekday(wd).lower() == config["schedule"].lower():
        logging.info("today's name matches schedule")
        repo = today.strftime("%Y-%m-%d")
        
    else:
        logging.info("today's name doesn't match schedule")
        backup_repo_list = get_backup_repo_list(config)
        if len(backup_repo_list) > 0:
            logging.info("list of repos: {}".format(backup_repo_list))
            repo = backup_repo_list[-1]
        else:
            logging.info("no existing repos")
            repo = today.strftime("%Y-%m-%d")

    logging.info("backup repo will be: {}".format(repo))
    
    # set the current repo name
    config["repo"] = repo


# retrive the list of backups
def get_backup_repo_list(config):
    regex = "(\d{4})-(\d{2})-(\d{2})"

    cmd =  [
        "ls", config["archive"]
    ]

    logging.info("retrieving list of repos from {}".format(config["archive"]))
    logging.debug("executing command: {}".format(str(cmd)))
    sp = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    stdout, stderr = sp.communicate()
    
    if sp.returncode > 0:
        logging.error(stdout)
        send_exit(config, action="ls archive", error=True)

    # generate backup list
    repos = [x.group(0) for x in re.finditer(regex, stdout)]
    repos.sort(key=lambda x: datetime.strptime(x, "%Y-%m-%d"))
    return repos


# retrive the list of backups
def get_backup_list(config):
    regex = "(\d{4})-(\d{2})-(\d{2})T(\d{2})_(\d{2})_(\d{2})(\S+)"

    cmd =  [
        config["cbbackupmgr"], "list", 
        "-a", config["archive"], 
        "-r", config["repo"]
    ]

    logging.info("retrieving list of backups from {}/{}".format(config["archive"], config["repo"]))
    logging.debug("executing command: {}".format(str(cmd)))
    sp = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    stdout, stderr = sp.communicate()
    
    if sp.returncode > 0:
        logging.error(stdout)
        send_exit(config, action="cbbackupmgr list", error=True)

    # generate backup list
    return [x.group(0) for x in re.finditer(regex, stdout)]


# initiate the backup of cluster
def backup(config):
    logging.info("backing up to repo: {}/{}".format(config["archive"], config["repo"]))
    logging.info("initiating backup against cluster: {}".format(config["cluster"]))
        
    cmd = [
        config["cbbackupmgr"], "backup",
        "-a", config["archive"],
        "-c", config["cluster"],
        "-p", config["password"],
        "-r", config["repo"],
        "-t", str(config["threads"]),
        "-u", config["username"],
        "--no-progress-bar"
    ]
    
    if config["purge"] is True:
        cmd.extend(["--purge"])

    logging.debug("executing command: {}".format(str(cmd)))
    sp = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    stdout, stderr = sp.communicate()
    
    if sp.returncode > 0:
        logging.error(stdout)
        send_exit(config, action="cbbackupmgr backup", error=True)
    else:
        logging.info(stdout)


# create the archive and repo
def create(config):
    if os.path.isdir("{}/{}".format(config["archive"], config["repo"])) is False:
        logging.info("creating repo: {}/{}".format(config["archive"], config["repo"]))
        
        cmd = [
            config["cbbackupmgr"], "config",
            "-a", config["archive"],
            "-r", config["repo"]
        ]

        logging.debug("executing command: {}".format(str(cmd)))
        sp = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        stdout, stderr = sp.communicate()
        
        if sp.returncode > 0:
            logging.error(stdout)
            send_exit(config, action="cbbackupmgr config", error=True)
        else:
            logging.info(stdout)


# compact the backups
def compact(config):
    backups = get_backup_list(config)
    if len(backups) > 0:
        logging.info("current backup list: {}".format(backups))
        
        # retrieve the last backup from list
        end = backups[-1]

        logging.info("initiating backup compaction of {}".format(end))
        
        cmd =  [
            config["cbbackupmgr"], "compact", 
            "-a", config["archive"], 
            "-r", config["repo"],
            "--backup", end
        ]

        logging.debug("executing command: {}".format(str(cmd)))
        sp = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        stdout, stderr = sp.communicate()
        
        if sp.returncode > 0:
            logging.error(stdout)
            send_exit(config, action="cbbackupmgr compact", error=True)
        else:
            logging.info(stdout)


# delete older repositories
def delete(config):
    backup_repo_list = get_backup_repo_list(config)
    if len(backup_repo_list) > config["keep"]:
        logging.info("current repo list: {}".format(backup_repo_list))
        logging.info("initiating repo deletion per keep: {}".format(config["keep"]))

        for i in range(len(backup_repo_list) - config["keep"]):
            delete_repo = backup_repo_list[i]
            logging.info("removing repo: {}/{}".format(config["archive"], delete_repo))

            cmd =  [
                config["cbbackupmgr"], "remove", 
                "-a", config["archive"], 
                "-r", delete_repo
            ]

            logging.debug("executing command: {}".format(str(cmd)))
            sp = subprocess.Popen(cmd, stdout=subprocess.PIPE)
            stdout, stderr = sp.communicate()
            
            if sp.returncode > 0:
                logging.error(stdout)
                send_exit(config, action="cbbackupmgr remove", error=True)
            else:
                logging.info(stdout)
    else:
        logging.info("current repo list: {}".format(backup_repo_list))
        logging.info("no repo delete per keep: {}".format(config["keep"]))


# log unsucessful and exit
def send_exit(config, action="backup_couchbase.py", error=False):
    if error is True:
        results = [{"host": config["cluster"], "action": action, "status": "CRITICAL"}]
    else:
        results = [{"host": config["cluster"], "action": action, "status": "OK"}]
    
    if config["file"]:
        send_file(results, config)
    else:
        send_stdout(results, config)

    sys.exit(0)

def send_stdout(results, config):
    for result in results:
        print(config["format"].format(**result))


def send_file(results, config):
    # [logging.info(config["format"].format(**result)) for result in results]
    for result in results:
        if result.get("status") in ("CRITICAL"):
            logging.critical(config["format"].format(**result))
        else:
            logging.info(config["format"].format(**result))

    try:
        with open(config["file"], 'w') as file:
            file.writelines(config["format"].format(**result) + '\n' for result in results)
    except Exception as e:
        logging.error(str(e))
        sys.exit(1)


# putting it all together
def main():
    config = get_config()

    logging.config.dictConfig(config["logging"])

    if config["verbose"]:
        logging.getLogger().setLevel(logging.DEBUG)

    if config["dump"]:
        print(yaml.dump(config, default_flow_style = False))
        sys.exit(0)

    try:
        get_backup_repo(config)
        create(config)
        backup(config)
        compact(config)
        delete(config)
    except Exception as e:
        logging.error("something went wrong executing backup script")
        send_exit(config, error=True)

    send_exit(config, error=False)

if __name__ == "__main__":
    main()