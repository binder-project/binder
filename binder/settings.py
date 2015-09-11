import os
import logging

if "BINDER_HOME" not in os.environ:
    raise Exception("BINDER_HOME environment variable must be set")
if "BINDER_PROJECT" not in os.environ:
    raise Exception("BINDER_PROJECT environment variable must be set")

provider = os.environ.get("KUBERNETES_PROVIDER")
if not provider:
    os.environ["KUBERNETES_PROVIDER"] = "gce"

# top level
class MainSettings(object):
    ROOT = os.environ["BINDER_HOME"]
    DOCKER_HUB_USER = "andrewosh"
    REGISTRY_NAME = "gcr.io/{}".format(os.environ["BINDER_PROJECT"])

# logging
class LogSettings(object):
    # server settings
    ROOT_DIRECTORY = "{}/logs/binder".format(os.environ["HOME"])
    APPS_DIRECTORY = "{}/logs/binder/apps".format(os.environ["HOME"])
    ROOT_FILE = "binder.log"
    LEVEL = logging.DEBUG

    HOST = "tcp://127.0.0.1"
    PORT = "9090"

# binderd
class BinderDSettings(object):
    BROKER_HOST = "tcp://127.0.0.1"
    BROKER_PORT = "9091"

    CONTROL_HOST = "tcp://127.0.0.1"
    CONTROL_PORT = "9092"

# monitoring
class MonitoringSettings(object): 
    APP_CRON_PERIOD = 5

# database

