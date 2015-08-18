import os
import logging

if "BINDER_HOME" not in os.environ:
    raise Exception("BINDER_HOME environment variable must be set")

provider = os.environ.get("KUBERNETES_PROVIDER")
if not provider:
    os.environ["KUBERNETES_PROVIDER"] = "gce"

ROOT = os.environ["BINDER_HOME"]
DOCKER_HUB_USER = "andrewosh"
REGISTRY_NAME = "gcr.io/generic-notebooks"

LOG_FILE = "/var/log/binder"
LOG_LEVEL = logging.INFO

APP_CRON_PERIOD = 5
