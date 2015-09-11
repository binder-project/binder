import os
import logging

if "BINDER_HOME" not in os.environ:
    raise Exception("BINDER_HOME environment variable must be set")

provider = os.environ.get("KUBERNETES_PROVIDER")
if not provider:
    os.environ["KUBERNETES_PROVIDER"] = "gce"

# top level
class MainSettings(object):
    ROOT = os.environ["BINDER_HOME"]
    DOCKER_HUB_USER = "andrewosh"
    REGISTRY_NAME = "gcr.io/binder-testing"

# logging
class LogSettings(object):
    # server settings
    APPS_DIRECTORY = os.path.join(LogSettings.ROOT_DIRECTORY, "apps")
    ROOT_DIRECTORY = "/var/log/binder"
    ROOT_FILE = "binder.log"
    LEVEL = logging.DEBUG

    HOST = "tcp://127.0.0.1"
    PORT = "9000"

# binderd
class BinderDSettings(object):
    BROKER_HOST = "tcp://127.0.0.1"
    BROKER_PORT = "9001"

    CONTROL_HOST = "tcp://127.0.0.1"
    CONTROL_PORT = "9002"

# monitoring
class MonitoringSettings(object): 
    APP_CRON_PERIOD = 5

# database

