import json
import os
import tempfile
import shutil
import time
import datetime

import pymongo

from binder.utils import make_dir
from binder.settings import LogSettings


class AppIndex(object):
    """
    Responsible for finding and managing metadata about apps.
    """

    TAG = "AppIndex"

    _singleton = None

    @staticmethod
    def get_index(*args, **kwargs):
        if not AppIndex._singleton:
            AppIndex._singleton = MongoAppIndex(*args, **kwargs)
        return AppIndex._singleton

    def create(self, spec):
        pass

    def get_app(self):
        pass

    def make_app_path(self, app):
        pass

    def update_build_state(self, app, state):
        pass

    def get_build_state(self, app):
        pass

    def update_last_build_time(self, app, time):
        pass

    def get_last_build_time(self, app):
        pass

    def save_app(self, app):
        pass


class FileAppIndex(AppIndex):
    """
    Finds/manages apps by searching for a certain directory structure in a directory hierarchy
    """

    TAG = "FileAppIndex"
    APPS_DIR = "apps"

    def __init__(self, root):
        self.apps_dir = os.path.join(root, FileAppIndex.APPS_DIR)
        make_dir(self.apps_dir)

    def _build_meta(self, spec, path):
        m = {
            "app": spec,
            "path": path,
        }
        return m

    def find_apps(self):
        apps = {}
        for path in os.listdir(self.apps_dir):
            app_path = os.path.join(self.apps_dir, path)
            spec_path = os.path.join(app_path, "spec.json")
            try:
                with open(spec_path, 'r') as sf:
                    spec = json.load(sf)
                    m = self._build_meta(spec, app_path)
                    apps[spec["name"]] = m
            except IOError as e:
                error_log(self.TAG,"Could not build app: {0}".format(path))
        return apps

    def create(self, spec):
        app_path = os.path.join(self.apps_dir, spec["name"])
        make_dir(app_path, clean=True)
        with open(os.path.join(app_path, "spec.json"), "w+") as spec_file:
            spec_file.write(json.dumps(spec))
        m = self._build_meta(spec, app_path)
        return m

    def get_app_path(self, app):
        return os.path.join(self.apps_dir, app.name)

    def make_app_path(self, app):
        path = self.get_app_path(app)
        make_dir(path)
        return path

    def update_build_state(self, app, state):
        state_file = tempfile.NamedTemporaryFile(delete=False)
        state_file.write(json.dumps({"build_state": state})+"\n")
        state_file.close()
        shutil.move(state_file.name, os.path.join(self.get_app_path(app), "build", ".build_state"))

    def get_build_state(self, app):
        path = os.path.join(self.get_app_path(app), "build", ".build_state")
        if not os.path.isfile(path):
            return None
        with open(path, "r") as state_file:
            state_json = json.loads(state_file.read())
            return state_json["build_state"]

    def save_app(self, app):
        info_log(self.TAG, "app currently must be rebuilt before each launch")


class MongoAppIndex(FileAppIndex):

    # TODO Mongo setup -> create a deprivileged user, etc. -> MongoAppIndex will also NOT 
    # inherit from FileAppIndex

    def __init__(self, root):
        super(MongoAppIndex, self).__init__(root)
        self._client = pymongo.MongoClient()
        self._app_db = self._client.app_db
        self._apps = self._app_db.apps

    def update_build_state(self, app, state):
        super(MongoAppIndex, self).update_build_state(app, state)

    def get_build_state(self, app):
        return super(MongoAppIndex, self).get_build_state(app)

    def update_last_build_time(self, app, time=None):
        if not time:
            time = datetime.datetime.now().strftime(LogSettings.TIME_FORMAT)
        query = {"app": app.name}
        update = {"$set": {"build_time": time}}
        self._apps.update_one(query, update, upsert=True)

    def get_last_build_time(self, app):
        query = {"app": app.name}
        projection = ["build_time"]
        res = self._apps.find_one(query, projection=projection)
        if not res:
            return None
        bt = res["build_time"]
        return datetime.datetime.strptime(bt, LogSettings.TIME_FORMAT)
        
        
class ServiceIndex(object):
    """
    Responsible for finding and managing metadata about services
    """
    
    TAG = "ServiceIndex"

    _singleton = None

    @staticmethod
    def get_index(*args, **kwargs):
        if not ServiceIndex._singleton:
            ServiceIndex._singleton = FileServiceIndex(*args, **kwargs)
        return ServiceIndex._singleton

    def find_services(self):
        pass

    def save_service(self, service):
        pass


class FileServiceIndex(ServiceIndex):
    """
    Finds/manages services by searching for a certain directory structure in a directory hierarchy
    """

    TAG = "FileServiceIndex"
    SERVICES_DIR = "services"

    def __init__(self, root):
        self.services_dir = os.path.join(root, self.SERVICES_DIR)

    def find_services(self):
        services = {}
        for name in os.listdir(self.services_dir):
            path = os.path.join(self.services_dir, name)
            for version in os.listdir(path):
                full_path = os.path.join(path, version)
                conf_path = os.path.join(full_path, "conf.json")
                last_build_path = os.path.join(full_path, ".last_build.json")
                try:
                    with open(conf_path, 'r') as cf:
                        s = {
                            "service": json.load(cf),
                            "path": full_path,
                            "name": name,
                            "version": version
                        }
                        if os.path.isfile(last_build_path):
                            with open(last_build_path, 'r') as lbf:
                                s["last_build"] = json.load(lbf)
                        services[name + '-' + version] = s
                except IOError:
                    error_log(self.TAG, "Could not build service: {0}".format(name + "-" + version))
        return services

    def save_service(self, service):
        j = service.to_json()
        with open(os.path.join(service.path, ".last_build.json"), "w") as f:
            f.write(json.dumps(j))
