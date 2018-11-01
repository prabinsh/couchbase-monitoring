# Couchbase Plugin
A plugin to monitor Couchbase REST APIs. Queries logs and searches for alert events. The ones found in Email Alerts of Couchbase console.  

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

### Format
Default service descriptions are built in the following format:
"{host}:{cluster name}:{alert}:{status}"

### Couchbase Alerts
This plugin comes pre-configured with a set of default alerts.
It will be necessary to update the alerts to reflect your Couchbase
environment. Updating alerts in config file will override defaults. Be sure to
include them if you are wanting to add addition checks.. 

## Usage
``` 
usage: logwatch_couchbase.py [-h] [--all] [--config CONFIG]
                             [--cluster CLUSTER] [--dump] [--file FILE]
                             [--format FORMAT] [--minutes MINUTES]
                             [--password PASSWORD] [--port {8091,18091}]
                             [--protocol {http,https}] [--username USERNAME]
                             [--verbose]

optional arguments:
  -h, --help            show this help message and exit
  --all                 Return results for all nodes in the cluster (default:
                        False)
  --config CONFIG       The path to YAML config file, reading config file
                        overrides args default values (default: None)
  --cluster CLUSTER     The hostname of the Couchbase cluster (default:
                        localhost)
  --dump                Dump the configuration values (default: False)
  --file FILE           The file to write results to (default: None)
  --format FORMAT       The format in which to print results. The str of
                        str.format() (default:
                        {host}:{cluster_name}:{alert}:{status})
  --minutes MINUTES     The number of minutes to search back (default: 5)
  --password PASSWORD   The password of the Couchbase cluster (default:
                        secret)
  --port {8091,18091}   The port of the Couchbase cluster (default: 8091)
  --protocol {http,https}
                        The protocol of the Couchbase cluster (default: http)
  --username USERNAME   The username of the Couchbase cluster (default:
                        readonly)
  --verbose             Enable debugging logging (default: False)

```
