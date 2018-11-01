# Couchbase Plugin
A plugin to monitor Couchbase REST APIs.

## Requirements
* Python requests module
* PyYAML

## Configuration
The set of metrics to monitor and thresholds for each metric are locally configured. Use --dump to create a yaml file and update according to environment.

### Minimum configuration, args
Make sure the following properties match your environment:
* cluster
* username
* password

### Format
Default service descriptions are built in the following format:
"{host}:{cluster name}:{label}:{metric}:{value}"

The configuration file documents how the service description is built and how to customize it.

### Couchbase metrics
This plugin comes pre-configured with a set of best-practice metrics.  It will be necessary to update the metric thresholds to reflect your Couchbase environment.

## Usage
``` 
usage: check_couchbase.py [-h] [--all] [--bucket BUCKET] [--cluster CLUSTER]
                          [--config CONFIG] [--dump] [--file FILE]
                          [--format FORMAT] [--port {8091,18091}]
                          [--password PASSWORD] [--fts-port {8094,18094}]
                          [--protocol {http,https}]
                          [--query-port {8093,18093}] [--username USERNAME]
                          [--verbose]

optional arguments:
  -h, --help            show this help message and exit
  --all                 Return results for all nodes in the cluster (default:
                        False)
  --bucket BUCKET       The bucket to return statistics on (default: all)
  --cluster CLUSTER     The hostname of the Couchbase cluster (default:
                        localhost)
  --config CONFIG       The path to YAML config file, reading config file
                        overrides args values (default: None)
  --dump                Dump the configuration values (default: False)
  --file FILE           The file to write results to (default: None)
  --format FORMAT       The format in which to print results. The str of
                        str.format() (default:
                        {host}:{cluster_name}:{label}:{metric}:{value})
  --port {8091,18091}   The port of the Couchbase cluster (default: 8091)
  --password PASSWORD   The password of the Couchbase cluster (default:
                        secret)
  --fts-port {8094,18094}
                        The port of the Couchbase cluster FTS service
                        (default: 8094)
  --protocol {http,https}
                        The protocol of the Couchbase cluster (default: http)
  --query-port {8093,18093}
                        The port of the Couchbase cluster Query service
                        (default: 8093)
  --username USERNAME   The username of the Couchbase cluster (default:
                        readonly)
  --verbose             Enable debugging logging (default: False)
```

### Original Nagios Plugin
https://github.com/couchbase-partners/nagios-plugin-couchbase