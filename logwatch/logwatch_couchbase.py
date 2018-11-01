#!/usr/bin/env python

import os
import sys
import argparse
import yaml
import logging
import logging.config
import requests
import json
import time
import re
from datetime import datetime, timedelta

parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument("--all",  dest="all", action="store_true", default=False, help="Return results for all nodes in the cluster")
parser.add_argument("--cluster",  dest="cluster", action="store", default="localhost", help="The hostname of the Couchbase cluster")
parser.add_argument("--config",  dest="config", action="store", help="The path to YAML config file, reading config file overrides args default values")
parser.add_argument("--dump",  dest="dump", action="store_true", default=False, help="Dump the configuration values")
parser.add_argument("--file",  dest="file", action="store", help="The file to write results to")
parser.add_argument("--format",  dest="format", action="store", default="{host}:{cluster_name}:{alert}:{status}", help="The format in which to print results. The str of str.format()")
parser.add_argument("--minutes",  dest="minutes", action="store", type=int, default=5, help="The number of minutes to search back")
parser.add_argument("--password",  dest="password", action="store", default="secret", help="The password of the Couchbase cluster")
parser.add_argument("--port",  dest="port", action="store", type=int, choices=[8091, 18091], default=8091, help="The port of the Couchbase cluster")
parser.add_argument("--protocol",  dest="protocol", action="store", choices=["http", "https"], default="http", help="The protocol of the Couchbase cluster")
parser.add_argument("--username",  dest="username", action="store", default="readonly", help="The username of the Couchbase cluster")
parser.add_argument("--verbose",  dest="verbose", action="store_true", default=False, help="Enable debugging logging")
args = parser.parse_args()

def get_config():
    config = vars(args)
    config.update(get_alerts())
    config.update(get_logging())

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


# define deault alerts to search for
def get_alerts():
    alerts = [
        {
            "name": "Node was auto-failed-over",
            "description": "The sending node has been failed over automatically.",
            "text": "Node .* was automatically failed over"
        },
        {
            "name": "Maximum number of auto-failed-over nodes was reached.",
            "description": "The auto-failover system stops auto-failover when the maximum number of spare nodes available has been reached.",
            "text": "Could not auto-failover more nodes *."
        },
        {
            "name": "Node wasn't auto-failedover as other nodes are down at the same time",
            "description": "Auto-failover does not take place if there is already a node down.",
            "text": "There was at least another node down"
        },
        {
            "name": "Node was not autofailed-over as there are not enough nodes in the cluster running the same service",
            "description": "You cannot support autofailover with less than three nodes.",
            "text": "Number of remaining nodes that are running .* service is .* You need at least .* nodes"
        },
        {
            "name": "Node was not autofailed-over as auto-failover for one or more services running on the node is disabled",
            "description": "Fired when a node is not autofailedover because auto-failover for one of the services running on the node is disabled.",
            "text": "Auto-failover for .* service is disabled"
        },
        {
            "name": "Node's IP address has changed unexpectedly",
            "description": "The IP address of the node has changed, which may indicate a network interface, operating system, or other network or system failure.",
            "text": "IP address seems to have changed"
        },
        {
            "name": "Disk space used for persistent storage has reached at least 90% of capacity",
            "description": "The disk device configured for storage of persistent data is nearing full capacity.",
            "text": "Approaching full disk warning"
        },
        {
            "name": "Metadata overhead is more than 50%",
            "description": "The amount of data required to store the metadata information for your dataset is now greater than 50% of the available RAM.",
            "text": "Metadata overhead warning"
        },
        {
            "name": "Bucket memory on a node is entirely used for metadata",
            "description": "All the available RAM on a node is being used to store the metadata for the objects stored. This means that there is no memory available for caching values. With no memory left for storing metadata, further requests to store data will also fail.",
            "text": "Hard out-of-memory error"
        },
        {
            "name": "Writing data to disk for a specific bucket has failed",
            "description": "The disk or device used for persisting data has failed to store persistent data for a bucket.",
            "text": "Write Commit Failure"
        },
        {
            "name": "Writing event to audit log has failed",
            "description": "Couchbase was unable to write an administrative event to the audit log.",
            "text": "Audit Write Failure"
        },
        {
            "name": "Approaching full Indexer RAM warning",
            "description": "The Indexer RAM utilization is approaching the configured quota. The indexer may soon pause.",
            "text": "Warning: approaching max index RAM"
        },
        {
            "name": "Remote mutation timestamp exceeded drift threshold",
            "description": "The remote mutation timestamp exceeded drift threshold warning.",
            "text": "Please ensure that NTP is set up correctly"
        },
        {
            "name": "Communication issues among some nodes in the cluster",
            "description": "There are some communication issues in some nodes within the cluster.",
            "text": "Warning: Node .* is having issues communicating with following nodes"
        }
    ]

    return {"alerts": alerts}


# logging default configuration to console
def get_logging():
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


# Executes a Couchbase REST API request and returns the output
def couchbase_request(host, port, uri, config):
    url = "{0}://{1}:{2}{3}".format(config["protocol"], host, str(port), uri)
    logging.debug("attempting couchbase request: {}".format(url))

    try:
        requests.packages.urllib3.disable_warnings(requests.packages.urllib3.exceptions.InsecureRequestWarning)
        f = requests.get(url, auth=(config["username"], config["password"]), verify=False)
        logging.debug(f)

        status = f.status_code

        if f.text:
            response = json.loads(f.text)

        # We can provide a helpful error message on 403
        if status == 403:
            if "permissions" in response:
                logging.error("{0}: {1}".format(response["message"], response["permissions"]))

        # Bail if status is anything but successful
        if status != 200:
            f.raise_for_status()

        return response
    except Exception as e:
        logging.error("failed to complete request to couchbase: {}".format(str(e)))
        return {}


# retrieve and process log events
def process_node_logs(host, port, cluster_name, config, results):
    tstamp = int((datetime.now() - timedelta(minutes=config["minutes"])).strftime("%s")) * 1000

    response = couchbase_request(host, port, "/logs", config)

    # validate response contains list
    if "list" in response:
        # number of items retureds from request
        logging.info("{} events returned from {}".format(len(response["list"]), host))

        # filter response data to events that happend minutes ago
        logging.info("looking for events with timestamp greater than {} milliseconds epoch".format(tstamp))
        events = [x for x in response["list"] if x["tstamp"] > tstamp]
        
        logging.info("{} events with greater timestamp".format(len(events)))

        # dump all the events to log
        for event in events:
            logging.debug("event: {}".format(json.dumps(event, indent=4, sort_keys=True)))

        # cycle through configered alerts and search each filtered event
        for alert in config["alerts"]:
            logging.debug("searching events for text: {}".format(alert["text"]))
            status = False
            for event in events:
                if re.search(alert["text"], event["text"], flags=re.IGNORECASE):
                    logging.debug("match found for event: {}".format(json.dumps(event, indent=4, sort_keys=True)))
                    status = True
                        
            results.append({"host": host, "cluster_name": cluster_name, "alert": alert["name"], "status": status})
    else:
        results.append({"host": host, "cluster_name": cluster_name, "alert": "Failed to complete request to Couchbase", "status": True})
    return results


# send results to console
def send_stdout(results, config):
    for result in results:
        print(config["format"].format(**result))


# send results to file
def send_file(results, config):
    # [logging.info(config["format"].format(**result)) for result in results]
    for result in results:
        if result.get("status"):
            logging.critical(config["format"].format(**result))
        else:
            logging.info(config["format"].format(**result))

    try:
        with open(config["file"], 'w') as file:
            file.writelines(config["format"].format(**result) + '\n' for result in results)
    except Exception as e:
        logging.error(str(e))
        sys.exit(1)


def main():
    config = get_config()
    results = []

    logging.config.dictConfig(config["logging"])

    if config["verbose"]:
        logging.getLogger().setLevel(logging.DEBUG)

    if config["dump"]:
        print(yaml.dump(config, default_flow_style = False))
        sys.exit(0)

    # retrieve info on cluster
    pools_default = couchbase_request(config["cluster"], config["port"], "/pools/default", config)

    # set the cluster name
    cluster_name = pools_default.get("clusterName", "default")

    # retrieve all nodes of cluster
    nodes = pools_default.get("nodes", [])

    for node in nodes:
        if config["all"] is False and "thisNode" not in node:
            continue

        if "thisNode" in node:
            host, port = (config["cluster"], config["port"])
        else:
            # node is formatted a hostname:port
            host, port = node["hostname"].split(":")
        
        # query and check for log events
        results = process_node_logs(host, port, cluster_name, config, results)

    if config["file"]:
        send_file(results, config)
    else:
        send_stdout(results, config)

if __name__ == "__main__":
    main()
