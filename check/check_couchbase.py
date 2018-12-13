#!/usr/bin/env python

"""
Collects statistics from the Couchbase REST API and forwards them to a 3rd party
  monitoring server.

Dependencies
 * python-requests
 * PyYAML
"""

import argparse
import json
import logging
import logging.config
import numbers
import operator
import os
import requests
import sys
import yaml
import re


# Basic setup
parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument("--all",  dest="all", action="store_true", default=False, help="Return results for all nodes in the cluster")
parser.add_argument("--bucket",  dest="bucket", action="store", default="all", help="The bucket to return statistics on")
parser.add_argument("--cluster",  dest="cluster", action="store", default="localhost", help="The hostname of the Couchbase cluster")
parser.add_argument("--config",  dest="config", action="store", help="The path to YAML config file, reading config file overrides args values")
parser.add_argument("--dump",  dest="dump", action="store_true", default=False, help="Dump the configuration values")
parser.add_argument("--file",  dest="file", action="store", help="The file to write results to")
parser.add_argument("--format",  dest="format", action="store", default="{host}:{cluster_name}:{label}:{metric}:{value}", help="The format in which to print results. The str of str.format()")
parser.add_argument("--port",  dest="port", action="store", type=int, choices=[8091, 18091], default=8091, help="The port of the Couchbase cluster")
parser.add_argument("--password",  dest="password", action="store", default="secret", help="The password of the Couchbase cluster")
parser.add_argument("--fts-port",  dest="fts_port", action="store", type=int, choices=[8094, 18094], default=8094, help="The port of the Couchbase cluster FTS service")
parser.add_argument("--protocol",  dest="protocol", action="store", choices=["http", "https"], default="http", help="The protocol of the Couchbase cluster")
parser.add_argument("--query-port",  dest="query_port", action="store", type=int, choices=[8093, 18093], default=8093, help="The port of the Couchbase cluster Query service")
parser.add_argument("--username",  dest="username", action="store", default="readonly", help="The username of the Couchbase cluster")
parser.add_argument("--verbose",  dest="verbose", action="store_true", default=False, help="Enable debugging logging")
args = parser.parse_args()


def main():
    config = get_config()
    results = []

    logging.config.dictConfig(config["logging"])

    if config["verbose"]:
        logging.getLogger().setLevel(logging.DEBUG)
    
    if config["dump"]:
        print(yaml.dump(config, default_flow_style = False))
        sys.exit(0)

    tasks = couchbase_request(config["cluster"], config["port"], "/pools/default/tasks", config)
    pools_default = couchbase_request(config["cluster"], config["port"], "/pools/default", config)

    # set the cluster name
    cluster_name = pools_default.get("clusterName", "default")

    # retrieve all nodes of cluster
    nodes = pools_default.get("nodes", [])

    if nodes == []:
        results.append({"host": config["cluster"], "metric": {"crit": "unhealthy", "warn": "unhealthy", "op": "=", "metric": "connectionStatus", "description": "communication with node"}, "value": "unhealthy", "label": "node"})

    for node in nodes:
        if config["all"] is False and "thisNode" not in node:
            continue

        if "thisNode" in node:
            host, port = config["cluster"], config["port"]
        else:
            # node is formatted a hostname:port
            host, port = node["hostname"].split(":")
        
        services = node["services"]

        results = process_node_stats(host, node, config, results)

        if "kv" in services:
            results = process_xdcr_stats(host, tasks, config, results)

            # all is a special case where we process stats for all buckets
            if config["bucket"] == "all":
                for bucket in couchbase_request(host, config["port"], "/pools/default/buckets?skipMap=true", config):
                    results = process_data_stats(host, bucket["name"], config["data"], config, results)
            else:
                results = process_data_stats(host, config["bucket"], config["data"], config, results)

        if "n1ql" in services:
            results = process_query_stats(host, config, results)

        if "fts" in services:
            results = process_fts_stats(host, config, results)

    if config["file"]:
        send_file(results, cluster_name, config)
    else:
        send_stdout(results, cluster_name, config)


# Attempts to load the configuration file overrides any args if set in this file
def get_config():
    config = vars(args)
    config.update(get_node())
    config.update(get_data())
    config.update(get_xdcr())
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


# Validates metric config
def validate_metric(metric, samples):
    if "metric" not in metric or metric["metric"] is None:
        logging.warning("Skipped: metric name not set")
        return False

    name = metric["metric"]

    if name not in samples:
        logging.warning("Skipped: metric does not exist: {0}".format(name))
        return False

    if "description" not in metric or metric["description"] is None:
        logging.warning("Skipped: service description is not set for metric: {0}".format(name))
        return False


# Formats numbers with a max precision 2 and removes trailing zeros
def pretty_number(f):
    value = str(round(f, 2)).rstrip("0").rstrip(".")

    if "." in value:
        return float(value)
    elif value == "":
        return 0
    else:
        return int(value)


# Averages multiple metric samples to smooth out values
def avg(samples):
    return sum(samples, 0) / len(samples)


# For dynamic comparisons
# Thanks to https://stackoverflow.com/a/18591880
def compare(inp, relate, cut):
    ops = {">": operator.gt,
           "<": operator.lt,
           ">=": operator.ge,
           "<=": operator.le,
           "=": operator.eq}
    return ops[relate](inp, cut)


# Determines metric status based on value and thresholds
def eval_status(value, critical, warning, op):
    if isinstance(critical, numbers.Number) and compare(value, op, critical):
        return 2, "CRITICAL"
    elif isinstance(critical, str) and compare(value, op, critical):
        return 2, "CRITICAL"
    elif isinstance(warning, numbers.Number) and compare(value, op, warning):
        return 1, "WARNING"
    elif isinstance(warning, str) and compare(value, op, warning):
        return 1, "WARNING"
    else:
        return 0, "OK"


# Evalutes data service stats and sends check results
def process_data_stats(host, bucket, metrics, config, results):
    logging.debug("Processing Data Stats...{}".format(host))
    s = couchbase_request(host, config["port"],  "/pools/default/buckets/{0}/stats".format(bucket), config)
    
    if "op" in s:
        stats = s["op"]["samples"]

        for m in metrics:
            if m["metric"] == "percent_quota_utilization":
                value = avg(stats["mem_used"]) / (avg(stats["ep_mem_high_wat"]) * 1.0) * 100
            elif m["metric"] == "percent_metadata_utilization":
                value = avg(stats["ep_meta_data_memory"]) / (avg(stats["ep_mem_high_wat"]) * 1.0) * 100
            elif m["metric"] == "disk_write_queue":
                value = avg(stats["ep_queue_size"]) + avg(stats["ep_flusher_todo"])
            elif m["metric"] == "total_ops":
                value = 0
                for op in ["cmd_get", "cmd_set", "incr_misses", "incr_hits", "decr_misses", "decr_hits", "delete_misses", "delete_hits"]:
                    value += avg(stats[op])
            else:
                if validate_metric(m, stats) is False:
                    continue

                value = avg(stats[m["metric"]])

            results.append({"host": host, "metric": m, "value": value, "label": bucket})

    return results


# Evaluates XDCR stats and sends check results
def process_xdcr_stats(host, tasks, config, results):
    logging.debug("Processing XDCR Stats...{}".format(host))
    for task in tasks:
        if task["type"] == "xdcr":
            if "xdcr" not in config or config["xdcr"] is None:
                logging.warning("XDCR is running but no metrics are configured")
                return results

            metrics = config["xdcr"]

            for m in metrics:
                # task["id"] looks like this: {GUID}/{source_bucket}/{destination_bucket}
                label = "xdcr {0}/{1}".format(task["id"].split("/")[1], task["id"].split("/")[2])

                if m["metric"] == "status":
                    value = task["status"]
                    results.append({"host": host, "metric": m, "value": value, "label": label})
                elif task["status"] in ["running", "paused"]:
                    # REST API requires the destination endpoint to be URL encoded.
                    destination = requests.utils.quote("replications/{0}/{1}".format(task["id"], m["metric"]), safe="")

                    uri = "/pools/default/buckets/{0}/stats/{1}".format(task["source"], destination)
                    stats = couchbase_request(host, config["port"], uri, config)

                    for node in stats.get("nodeStats", []):
                        # node is formatted as host:port
                        if host == node.split(":")[0]:
                            if len(stats["nodeStats"][node]) == 0:
                                logging.error("Invalid XDCR metric: {0}".format(m["metric"]))
                                continue

                            value = avg(stats["nodeStats"][node])
                            results.append({"host": host, "metric": m, "value": value, "label": label})

    return results


# Evaluates query service stats and sends check results
def process_query_stats(host, config, results):
    logging.debug("Processing Query Stats...{}".format(host))
    if "query" not in config:
        logging.warning("Query service is running but no metrics are configured")
        return results

    metrics = config["query"]
    stats = couchbase_request(host, config["query_port"],  "/admin/stats", config, "query")

    for m in metrics:
        if validate_metric(m, stats) is False:
            continue

        value = stats[m["metric"]]

        # Convert nanoseconds to milliseconds
        if m["metric"] in ["request_timer.75%", "request_timer.95%", "request_timer.99%"]:
            value = value / 1000 / 1000

        results.append({"host": host, "metric": m, "value": value, "label": "query"})

    return results


# Evaluates FTS service stats and sends check results
def process_fts_stats(host, config, results):
    logging.debug("Processing FTS Stats...{}".format(host))
    if "fts" not in config or config["fts"] is None:
        logging.warning("FTS service is running but no metrics are configured")
        return results

    metrics = config["fts"]
    stats = couchbase_request(host, config["fts_port"],  "/api/nsstats", config, "fts")

    for m in metrics:
        value = 0

        # stat name is formatted "bucket:index:metric"
        # we are only concerned about totals across all indexes
        for stat in stats:
            metric = stat.split(":")

            if len(metric) != 3 or m["metric"] != metric[2]:
                continue

            label = "fts {0}:{1}".format(metric[0], metric[1])
            value = stats[stat]

            results.append({"host": host, "metric": m, "value": value, "label": label})

    return results


# Evaluates node stats and sends check results
def process_node_stats(host, stats, config, results):
    logging.debug("Processing Nodes Stats...{}".format(host))
    metrics = config["node"]

    for m in metrics:
        if validate_metric(m, stats) is False:
            continue

        value = str(stats[m["metric"]])

        results.append({"host": host, "metric": m, "value": value, "label": "node"})

    return results


# Executes a Couchbase REST API request and returns the output
def couchbase_request(host, port, uri, config, service=None):
    url = "{0}://{1}:{2}{3}".format(config["protocol"], host, str(port), uri)
    logging.debug("Attempting Couchbase Request: {}".format(url))

    try:
        requests.packages.urllib3.disable_warnings(requests.packages.urllib3.exceptions.InsecureRequestWarning)
        f = requests.get(url, auth=(config["username"], config["password"]), verify=False, timeout=10)
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
        logging.error("Failed to complete request to Couchbase: {}".format(str(e)))
        return {}


def formatted_output_list(results, cluster_name, config):
    lines = []
    for result in results:
        host = result["host"]
        metric = result["metric"]
        value = result["value"]
        label = result["label"]
        
        metric.setdefault("crit", None)
        metric.setdefault("warn", None)
        metric.setdefault("op", ">=")
        metric.setdefault("metric", None)
        metric.setdefault("description", None)

        if metric["op"] not in [">", ">=", "=", "<=", "<"]:
            logging.warning("Skipped metric: \"{0}\", invalid operator: {1}".format(metric["description"], metric["op"]))
            continue

        if isinstance(value, numbers.Number):
            value = pretty_number(value)

        status, status_text = eval_status(value, metric["crit"], metric["warn"], metric["op"])

        items = {"host": host}
        items["cluster_name"] = cluster_name
        items["label"] = label
        items["value"] = value
        items["metric"] = metric["metric"]
        items["warn"] = metric["warn"]
        items["crit"] = metric["crit"]
        items["op"] = metric["op"]
        items["description"] = metric["description"]
        items["status"] = status_text

        lines.append(config["format"].format(**items))
    return lines


def send_stdout(results, cluster_name, config):
    lines = formatted_output_list(results, cluster_name, config)
    for line in lines:
        print(line)


def send_file(results, cluster_name, config):
    lines = formatted_output_list(results, cluster_name, config)
    # [logging.info(line) for line in lines]
    for line in lines:
        if re.search("CRITICAL", line):
            logging.critical(line)
        elif re.search("WARNING", line):
            logging.warning(line)
        else:
            logging.info(line)

    try:
        with open(config["file"], 'w') as file:
            file.writelines(line + '\n' for line in lines)
    except Exception as e:
        logging.error(str(e))


def get_node():
    node = [
        {
            "metric": "status",
            "description": "health status",
            "warn": "warmup",
            "crit": "unhealthy",
            "op": "="
        },
        {
            "metric": "clusterMembership",
            "description": "cluster membership",
            "warn": "inactiveAdded",
            "crit": "inactiveFailed",
            "op": "="
        }
    ]

    return {"node": node}

def get_data():
    data = [
        {
            "metric": "percent_quota_utilization",
            "description": "percent bucket quota used",
            "warn": 95,
            "crit": 95,
            "op": ">="
        },
        {
            "metric": "percent_metadata_utilization",
            "description": "percent bucket quota used by metadata",
            "warn": 50,
            "crit": 50,
            "op": ">="
        },
        {
            "metric": "disk_write_queue",
            "description": "items in disk write queue",
            "warn": 10000,
            "crit": 10000,
            "op": ">="
        },
        {
            "metric": "curr_connections",
            "description": "client connections",
            "warn": 10000,
            "crit": 10000,
            "op": ">="
        },
        {
            "metric": "ep_dcp_replica_backoff",
            "description": "internal replication backoffs",
            "warn": 1,
            "crit": 1,
            "op": ">="
        },
        {
            "metric": "ep_dcp_xdcr_backoff",
            "description": "XDCR backoffs",
            "warn": 1,
            "crit": 1,
            "op": ">="
        },
        {
            "metric": "ep_oom_errors",
            "description": "out of memory errors",
            "warn": 1,
            "crit": 1,
            "op": ">="
        },
        {
            "metric": "ep_tmp_oom_errors",
            "description": "temporary out of memory errors",
            "warn": 1,
            "crit": 1,
            "op": ">="
        },
        {
            "metric": "vb_active_resident_items_ratio",
            "description": "percent active items in memory",
            "warn": 15,
            "crit": 15,
            "op": "<="
        },
        {
            "metric": "vb_replica_resident_items_ratio",
            "description": "percent replica items in memory",
            "warn": 15,
            "crit": 15,
            "op": "<="
        },
        {
            "metric": "vb_avg_total_queue_age",
            "description": "disk write queue average age",
            "warn": 5,
            "crit": 5,
            "op": ">="
        }
    ]

    return {"data": data}


def get_xdcr():
    xdcr = [
        {
            "metric": "status",
            "description": "replication status",
            "warn": "paused",
            "crit": "notRunning",
            "op": "="
        }
    ]

    return {"xdcr": xdcr}


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


if __name__ == "__main__":
    main()
