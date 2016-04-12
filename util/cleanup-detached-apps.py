"""
Cleanup apps that have lost their proxy routes, but are older than a certain duration (1 hour for now)
"""
from datetime import datetime, timedelta
import subprocess
import re

from dateutil import parser, tz
import requests
from binder.cluster import ClusterManager

app_re = re.compile('\d+')

def get_apps():
    res = requests.get('http://localhost:8083/api/v1/namespaces')
    namespaces = res.json()
    for ns in namespaces['items']:
       yield (ns['metadata']['name'], ns['metadata']['creationTimestamp'])

def cleanup():
    cm = ClusterManager.get_instance()
    all_routes = set(cm._get_inactive_routes(0))
    for name, timestamp in get_apps():
        if (name not in all_routes) and app_re.match(name):
            print "going to delete app: {0}".format(name)
            subprocess.check_output(['kubectl.sh', 'delete', 'namespace', name])

cleanup()
   
