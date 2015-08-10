import json
import os

from binder.utils import make_dir


class AppIndex(object):
    """
    Responsible for finding and managing metadata about apps.
    """

    _singleton = None

    @staticmethod
    def get_index(*args, **kwargs):
        if not AppIndex._singleton:
            AppIndex._singleton = FileAppIndex(*args, **kwargs)
        return AppIndex._singleton

    def get_app(self):
        pass

    def make_app_path(self, app):
        pass

    def save_app(self, app):
        pass


class FileAppIndex(AppIndex):
    """
    Finds/manages apps by searching for a certain directory structure in a directory hierarchy
    """

    APP_DIR = "apps"

    def __init__(self, root):
        self.app_dir = os.path.join(root, self.APP_DIR)
        make_dir(self.app_dir)

    def find_apps(self):
        apps = {}
        for path in os.listdir(self.app_dir):
            app_path = os.path.join(self.app_dir, path)
            spec_path = os.path.join(app_path, "spec.json")
            try:
                with open(spec_path, 'r') as sf:
                    spec = json.load(sf)
                    m = {
                        "app": spec,
                        "path": app_path,
                    }
                    apps[spec["name"]] = m
            except IOError as e:
                print("Could not build app: {0}".format(path))
        return apps

    def make_app_path(self, app):
        path = os.path.join(self.app_dir, app.name)
        make_dir(path, clean=True)
        return path

    def save_app(self, app):
        print("app currently must be rebuilt before each launch")


class ServiceIndex(object):
    """
    Responsible for finding and managing metadata about services
    """

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
                            "name": path,
                            "version": version
                        }
                        if os.path.isfile(last_build_path):
                            with open(last_build_path, 'r') as lbf:
                                s["last_build"] = json.load(lbf)
                        services[path + '-' + version] = s
                except IOError:
                    print("Could not build service: {0}".format(path + "-" + version))
        return services

    def save_service(self, service):
        j = service.to_json()
        with open(os.path.join(service.path, ".last_build.json"), "w") as f:
            f.write(json.dumps(j))