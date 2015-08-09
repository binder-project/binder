if "POD_SERVER_HOME" not in os.environ:
    raise Exception("POD_SERVER_HOME environment variable must be set")

ROOT = os.environ["POD_SERVER_HOME"]
DOCKER_USER = "andrewosh"