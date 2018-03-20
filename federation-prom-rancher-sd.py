#!/usr/bin/python3

import time
import urllib.parse
import urllib.request
from urllib.error import URLError, HTTPError
import json
import shutil
import sys
import os

# method to check authentication error
def get_www_authenticate_header(api_url):
    try:
        resp = urllib.request.urlopen(api_url)
        response = (resp.read())
    except urllib.error.HTTPError as error:
        response = (error.info()['Www-Authenticate'])
    return json.loads(response.decode('utf8 '))


def manage_auth(user, password, url, uri):
    # create a password manager
    password_mgr = urllib.request.HTTPPasswordMgrWithDefaultRealm()

    # Add the username and password.
    # If we knew the realm, we could use it instead of None.
    password_mgr.add_password(None, url, user, password)

    handler = urllib.request.HTTPBasicAuthHandler(password_mgr)

    # create "opener" (OpenerDirector instance)
    opener = urllib.request.build_opener(handler)

    # use the opener to fetch a URL
    opener.open(url+uri)

    # Install the opener.
    # Now all calls to urllib.request.urlopen use our opener.
    urllib.request.install_opener(opener)

def get_current_metadata_entry(entry):
    headers = {
        'User-Agent': "prom-rancher-sd/0.1",
        'Accept': 'application/json'
    }
    req = urllib.request.Request(entry, headers=headers)
    with urllib.request.urlopen(req) as response:
        return json.loads(response.read().decode('utf8 '))


def is_promotheus_service(service):

    return "prometheus" == service['name'] and "publicEndpoints" in service and service['publicEndpoints'] is not None

def get_prometheus_hosts(rancher_host):
    prometheus_hosts = []
    for project in get_current_metadata_entry(rancher_host + '/projects')['data']:
        for service in get_current_metadata_entry(rancher_host + '/projects/'+project['id']+'/services')['data']:
            if is_promotheus_service(service):
                prometheus_hosts.append(prometheus_monitoring_config(service, project['name']))
    return prometheus_hosts

def prometheus_monitoring_config(service, project_name):
    return {
        "targets": [publicEndpoint['ipAddress'] + ':' + str(publicEndpoint['port']) for publicEndpoint in service['publicEndpoints']]    }

def write_config_file(filename, content):
    tmpfile = filename+'.temp'
    with open(tmpfile, 'w') as config_file:
        print(json.dumps(content, indent=2),file=config_file)
    shutil.move(tmpfile,filename)

if __name__ == '__main__':

    try:
        apikey = os.environ["RANCHER_ACCESS_KEY"]
        secretkey = os.environ["RANCHER_SECRET_KEY"]
        url = os.environ["RANCHER_URL"]
    except KeyError:
        print("Please set the environment variables RANCHER_ACCESS_KEY RANCHER_SECRET_KEY RANCHER_URL")
        sys.exit(1)
    manage_auth( apikey, secretkey, url, '/token')
    retry = 0
    max_retry = 5
    while retry < max_retry:
        try:
            time.sleep(5)
            write_config_file('prometheus-federation.json', get_prometheus_hosts(url))
        except HTTPError as e:
            if e.code == 401:
                print('Authentication error please check your RANCHER_ACCESS_KEY and RANCHER_SECRET_KEY')
                sys.exit(1)
            else:
                print('The server couldn\'t fulfill the request. Error code:', e.code, 'Reason:', e.reason)
                retry += 1
        except URLError as e:
            print('We failed to reach a server.')
            print('Reason: ', e.reason)
            retry += 1
