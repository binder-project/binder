#!/usr/bin/python
import argparse
import os
import shutil
import json
import subprocess

if "POD_SERVER_HOME" not in os.environ: 
    raise Exception("POD_SERVER_HOME environment variable must be set")

ROOT = os.environ["POD_SERVER_HOME"]
DOCKER_USER = "andrewosh"

"""
Utilities
"""

def fill_template(template_path, params):
    res = [(re.compile(k), params[k]) for k in params.keys()]
    with open(tempate_path, 'w') as template:
        raw = template.read()
        replaced = raw
        for pattern, new in res:
            replaced = pattern.sub(replaced, new)
        template.write(replaced)

"""
Indices
"""

class AppIndex(object):
    """
    Responsible for finding and managing metadata about apps.
    """

    @staticmethod
    def get_index(*args, **kwargs):
        return FileAppIndex(*args, **kwargs)

    def find_apps(self):
        pass

    def save_app(self, app):
        pass


class ModuleIndex(object):
    """
    Responsible for finding and managing metadata about modules
    """

    @staticmethod
    def get_index(*args, **kwargs):
        return FileModuleIndex(*args, **kwargs)

    def find_modules(self):
        pass

    def save_module(self, module):
        pass


class FileModuleIndex(ModuleIndex):
    """
    Finds/manages modules by searching for a certain directory structure in a directory hierarchy
    """
    MODULE_DIR = "modules"
    def __init__(self, root):
        self.module_dir = os.path.join(root, self.MODULE_DIR)

    def get_modules(self):
        try:
            modules = {}
            for path in os.listdir(self.module_dir):
                mod_path = os.path.join(self.module_dir, path)
                for version in os.listdir(mod_path):
                    full_path = os.path.join(mod_path, version)
                    conf_path = os.path.join(full_path, "conf.json")
                    last_build_path = os.path.join(full_path, ".last_build.json")
                    with open(conf_path, 'r') as cf:
                        m = {
                            "module": json.load(cf),
                            "path": full_path,
                            "name": path,
                            "version": version
                        }
                        if os.path.isfile(last_build_path):
                            with open(last_build_path, 'r') as lbf:
                                m["last_build"] = json.load(lbf)
                        modules[path + '-' + version] = m
            return modules
        except IOError as e:
            print e
        return {}

    def save_module(self, path, module):
        j = module.to_json()
        with open(os.path.join(path, ".last_build.json"), "w") as f:
            f.write(json.dumps(j))


class FileAppIndex(AppIndex):
    """
    Finds/manages apps by searching for a certain directory structure in a directory hierarchy
    """
    APP_DIR = "apps"
    def __init__(self, root):
        app_dir = os.path.join(root, self.APP_DIR)

    def get_apps(self):
        pass

    def save_app(self):
        pass

"""
Models
"""

class App(object):

    index = AppIndex.get_index(ROOT)

    @staticmethod
    def get_app(name=None):
        apps = App.index.get_apps()
        if not name:
            return [App(a) for a in apps]
        return App(apps.get(name))

    def __init__(self, meta):
        pass

    def build(self):
        pass

    def deploy(self, mode):
        pass

    def destroy(self):
        pass


class Module(object):

    index = ModuleIndex.get_index(ROOT)

    @staticmethod
    def get_module(name=None):
        modules = Module.index.get_modules()
        if not name:
            return modules
        return Module(modules.get(name))

    def __init__(self, meta):
        self._json = meta["module"]
        self.path = meta["path"]
        self.name = meta["name"]
        self.version = meta["version"]
        self.last_build = meta.get("last_build")
        self.images = self._json.get("images")
        self.parameters = self._json.get("parameters")

    def build(self):
        # only initiate the build if the current spec is different than the last spec built
        if self._json != self.last_build:

            # clean up the old build
            build_path = os.path.join(self.path, "build")
            if os.path.isdir(build_path):
                os.rmdir(temp_path)
                os.mkdir(temp_path)

            # copy new file and replace all template placeholders with parameters
            build_dirs = ["components", "deployments", "images"]
            for bd in build_dirs:
                bd_path = os.path.join(build_path, bd)
                shutil.copytree(os.path.join(self.path, bd), bd_path)
                for root, dirs, files in os.walk(os.path.join(build_path, bd)):
                    for f in files:
                        fill_template(os.path.join(root, f), self.parameters)

            # now that all templates are filled, build/upload images
            for image in self.images:
                try:
                    image_name = DOCKER_USER + "/" + self.name + "-" + self.version + "-" + image
                    subprocess.check_call(['docker', 'build', '-t', image_name, self.images[image]])
                    subprocess.check_call(['docker', 'push', image_name])
                except CalledProcessError as e:
                    print e

            # write latest build parameters
            self.index.save_app(self)

            print("Successfully build {0}".format(self.name + "-" + self.version))

    def deploy(self, mode):
        pass

    def to_json(self):
        return self._json

"""
Build section
"""


def handle_build(args):
    print("In handle_build, args: {0}".format(str(args)))
    
    if args.subcmd == "module":
        build_module(args)
    elif args.subcmd == "app":
        build_app(args)

def build_module(args):
    module = Module.get_module(name=args.name)
    if module:
        module.build()
    else:
        print("Module {0} not found".format(module))

def build_app(args):
    app = App.get_app(name=args.name)
    if app:
        app.build()
    else:
        print("App {0} not found".format(app))

def _build_subparser(parser):
    p = parser.add_parser("build", description="Build modules or applications")
    s = p.add_subparsers(dest="subcmd")

    module = s.add_parser("module")
    module.add_argument("name", help="Name of module to build", nargs="?")
    module.add_argument("--upload", required=False, help="Upload module after building")
    module.add_argument("--all", required=False, help="Build all modules")

    app = s.add_parser("app")
    app.add_argument("name", help="Name of app to build", nargs="*")

"""
List section
"""

def handle_list(args):
    print("In handle_list, args: {0}".format(str(args)))

    app_index, module_index = IndexFactory.get_indices(ROOT)

    if args.subcmd == "modules":
        list_modules(module_index)
    elif args.subcmd == "apps":
        list_apps(app_index)

def list_modules(module_index):
    modules = module_index.get_modules()
    print "Available modules:"
    for module in modules:
        print(" {0}".format(module['name']))
        for version in module['versions']:
            print("  {0} - last built: {1}".format(version['name'], version['build_time']))

def list_apps(app_index):
    apps = app_index.get_apps()
    print "Available apps:"
    for app in apps:
        print(" {0} - last built: {1}`".format(app['name'], app['build_time']))

def _list_subparser(parser):
    p = parser.add_parser("list", description="List modules or applications")
    s = p.add_subparsers(dest="subcmd")

    mod_parser = s.add_parser("modules")
    app_parser = s.add_parser("apps")

"""
Deploy section
"""

def handle_deploy(args):
    print("In handle_deploy, args: {0}".format(str(args)))

    if args.subcmd == "module":
        list_modules()
    elif args.subcmd == "app":
        list_apps()

def deploy_app(app):
    pass

def _deploy_subparser(parser):
    p = parser.add_parser("deploy", description="Deploy applications")
    s = p.add_subparsers(dest="subcmd")

    s.add_parser("module")
    s.add_parser("app")

"""
Upload section
"""

def handle_upload(args):
    print("In handle_upload, args: {0}".format(str(args)))

def _upload_subparser(parser):
    p = parser.add_parser("upload", description="Upload modules or applications")
    s = p.add_subparsers(dest="subcmd")

    s.add_parser("module")
    s.add_parser("app")

"""
Main section
"""

if __name__ == "__main__":

    choices = {
        "list": {
            "parser": _list_subparser,
            "handler": handle_list
        },
        "deploy": {
            "parser": _deploy_subparser,
            "handler": handle_deploy
        },
        "upload": {
            "parser": _upload_subparser,
            "handler": handle_upload
        },
        "build": {
            "parser": _build_subparser,
            "handler": handle_build
        }
    }

    parser = argparse.ArgumentParser(description="Launch generic Python applications on a Kubernetes cluster")
    subparsers = parser.add_subparsers(dest="cmd")
    for c in choices:
        choices[c]["parser"](subparsers)

    args = parser.parse_args()

    for c in choices:
        if args.cmd == c:
            choices[c]["handler"](args)
            break

