#!/usr/bin/env python

import argparse
import ConfigParser
import logging
import requests
import os
import json

logger = logging.getLogger('checkmk_livestatus')
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)

# Producer for the NERDS project to be used with the NagiosXI API.
# (http://github.com/fredrikt/nerds/)

COLUMNS = [
    'host_name',     # Needed for NERDS formatting
    'host_address',  # Needed for NERDS formatting
    'host_alias',
    'check_command',
    'name',
    'display_name',
    'last_check',
    'performance_data',
    'status_text'
]

MAPPING = {
    'name': 'description',
    'status_text': 'plugin_output',
    'performance_data': 'perf_data',
    }


def only_fields(_dict, keys=COLUMNS, rename=MAPPING):
    return {rename.get(key, key): _dict.get(key) for key in keys}


def nerds_base(host_name, host_address, host_alias):
    return {
        'host': {
            'name': host_name,
            'version': '1',
            'nagiosxi_api': {
                'host_name': host_name,  # why repeat?
                'host_alias': host_alias,
                'host_address': host_address,
                'checks': [],
            }
        }
    }


def nerds_format(services):
    _dict = {}
    for service in services:
        host_name = service.pop('host_name')
        host_address = service.pop('host_address')
        host_alias = service.pop('host_alias', None)
        if host_name not in _dict:
            _dict[host_name] = nerds_base(host_name, host_address, host_alias)
        _service = _dict[host_name]
        _service['host']['nagiosxi_api']['checks'].append(service)
    return _dict.values()


def produce(conf, dry_run, out_dir):
    base_url = conf.get('api', 'url')
    api_key = conf.get('api', 'api_key')

    url = base_url+'/objects/servicestatus'
    params = {'apikey': api_key}
    req = requests.get(url, params=params)

    resp = req.json()
    raw_services = resp.get("servicestatuslist", {}).get("servicestatus", [])
    services = [only_fields(service) for service in raw_services]
    nerds = nerds_format(services)
    for nerds_dict in nerds:
        write_json(nerds_dict, dry_run, out_dir)


def write_json(nerds_dict, dry_run=False, out_dir='./json'):
    if dry_run:
        print json.dumps(nerds_dict, sort_keys=True, indent=4)
    else:
        file_name = '{}.json'.format(nerds_dict['host']['name'])
        path = os.path.join(out_dir, file_name)
        with open(path, 'w') as f:
            json.dump(nerds_dict, f, sort_keys=True, indent=4)


def init_config(path):
    """
    Initializes the configuration file located in the path provided.
    """
    try:
        config = ConfigParser.SafeConfigParser()
        config.read(path)
        return config
    except IOError as (errno, strerror):
        logger.error('I/O error({0}): {1}'.format(errno, strerror))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-o', '--out-dir', default='./json/', nargs='?', help='Path to output directory.')
    parser.add_argument('-n', '--dry-run', action='store_true', default=False, help='Print output to  std-out.')
    parser.add_argument('-C', nargs='?', help='Path to configuration file')
    args = parser.parse_args()

    if args.C:
        config = init_config(args.C)
    else:
        logger.error('Please provide a configuration file with -C')

    if not os.path.exists(args.out_dir) and not args.dry_run:
        os.makedirs(args.out_dir)

    # get nagios service status
    produce(config, args.dry_run, args.out_dir)


if __name__ == '__main__':
    main()
