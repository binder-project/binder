#!/usr/bin/python
import argparse
import os
import shutil
import json
import subprocess
import re

from memoized_property import memoized_property

if "POD_SERVER_HOME" not in os.environ:
    raise Exception("POD_SERVER_HOME environment variable must be set")

ROOT = os.environ["POD_SERVER_HOME"]
DOCKER_USER = "andrewosh"

"""
Utilities
"""

def namespace_params(ns, params):
    ns_params = {}
    for p in params:
        ns_params['app.' + p] = params[p]
    return ns_params

def fill_template_string(template, params):
    res = [(re.compile("{{" + k + "}}"), params[k]) for k in params if isinstance(params[k], basestring)]
    replaced = template
    for pattern, new in res:
        replaced = pattern.sub(new, replaced)
    return replaced

def fill_template(template_path, params):
    try:
        res = [(re.compile("{{" + k + "}}"), params[k]) for k in params if isinstance(params[k], basestring)]
        with open(template_path, 'r+') as template:
            raw = template.read()
        with open(template_path, 'w') as template:
            replaced = raw
            for pattern, new in res:
                replaced = pattern.sub(new, replaced)
            template.write(replaced)
    except (IOError, TypeError) as e:
        print("Could not fill template {0}: {1}".format(template_path, e))

"""
Cluster management
"""

class ClusterManager(object):

    @staticmethod
    def get_instance():
        return KubernetesManager()

    def deploy_app(self, app_dir):
        """
        Deploys an app on the cluster. Returns the IP/port combination for the notebook server
        """
        pass

    def destroy_app(self, app_id):
        pass

    def list_apps(self):
        pass

class KubernetesManager(ClusterManager):

    def deploy_app(self, app_dir):
        for f in os.listdir(app_dir):
            path = os.path.join(app_dir, f)
            try:
                subprocess.check_call(['kubectl.sh', 'create', '-f', path])
            except subprocess.CalledProcessError as e:
                print("Could not deploy {0} on Kubernetes cluster".format(path))
        # TODO get the return IP/port

    def destroy_app(self, app_id):
        pass

    def list_apps(self):
        pass

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

    def get_app(self):
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

    def find_modules(self):
        modules = {}
        for path in os.listdir(self.module_dir):
            mod_path = os.path.join(self.module_dir, path)
            for version in os.listdir(mod_path):
                full_path = os.path.join(mod_path, version)
                conf_path = os.path.join(full_path, "conf.json")
                last_build_path = os.path.join(full_path, ".last_build.json")
                try:
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
                except IOError as e:
                    print("Could not build module: {0}".format(path + "-" + version))
        return modules

    def save_module(self, module):
        j = module.to_json()
        with open(os.path.join(module.path, ".last_build.json"), "w") as f:
            f.write(json.dumps(j))


class FileAppIndex(AppIndex):
    """
    Finds/manages apps by searching for a certain directory structure in a directory hierarchy
    """

    APP_DIR = "apps"

    def __init__(self, root):
        self.app_dir = os.path.join(root, self.APP_DIR)

    def find_apps(self):
        apps = {}
        for path in os.listdir(self.app_dir):
            app_path = os.path.join(self.app_dir, path)
            spec_path = os.path.join(app_path, "spec.json")
            try:
                with open(spec_path, 'r') as sf:
                    m = {
                        "app": json.load(sf),
                        "path": app_path,
                    }
                    apps[path] = m
            except IOError as e:
                print("Could not build app: {0}".format(path))
        return apps

    def save_app(self, app):
        print("app currently must be rebuilt before each launch")


"""
Models
"""

class App(object):

    index = AppIndex.get_index(ROOT)

    @staticmethod
    def get_app(name=None):
        apps = App.index.find_apps()
        if not name:
            return [App(a) for a in apps.values()]
        return App(apps.get(name))

    def __init__(self, meta):
        self._json = meta["app"]
        self.path = meta["path"]
        self.name = self._json.get("name")
        self.modules = self._json.get("modules")
        self.config_scripts = self._json.get("config_scripts")
        self.requirements = self._json.get("requirements")
        self.repo = os.path.join(self.path, self._json.get("root"))

        self.build_time = 0

    def _get_app_params(self):
        # TODO some of these should be moved into some sort of a Defaults class (config file?)
        return namespace_params("app", {
                "num_replicas": "5",
                "project_name": self.name,
                "id": self.name + "-" + self._get_deployment_id(),
                "notebooks_name": self.name + "-" + "notebooks",
                "notebooks_image": DOCKER_USER + "/" + self.name,
                "notebooks_port": "8888"
        })

    def _get_deployment_id(self):
        import time
        return str(hash(time.time()))

    def _get_modules(self):
        return [Module.get_module(mod_json["name"], mod_json["version"]) for mod_json in self.modules]

    def build(self):
        success = True

        # clean up the old build
        build_path = os.path.join(self.path, "build")
        if os.path.isdir(build_path):
            shutil.rmtree(build_path)
            os.mkdir(build_path)

        # ensure that the module dependencies are all build
        print "Building module dependencies..."
        for module in self._get_modules():
            module.build()

        # copy new file and replace all template placeholders with parameters
        print "Copying files and filling templates..."
        core_images_path = os.path.join(ROOT, "core")
        for img in os.listdir(core_images_path):
            img_path = os.path.join(core_images_path, img)
            bd_path = os.path.join(build_path, img)
            shutil.copytree(img_path, bd_path)
            for root, dirs, files in os.walk(bd_path):
                for f in files:
                    fill_template(os.path.join(root, f), self._json)

        # make sure the base image is built
        print "Building base image..."
        try:
            base_img = os.path.join(core_images_path, "base")
            image_name = DOCKER_USER + "/" + "generic-base"
            subprocess.check_call(['docker', 'build', '-t', image_name, base_img])
            subprocess.check_call(['docker', 'push', image_name])
        except subprocess.CalledProcessError as e:
            print("Could not build the base image: {0}".format(e))
            success = False

        # construct the app image Dockerfile
        print "Building app image..."
        app_img_path = os.path.join(build_path, "app")
        shutil.copytree(self.repo, os.path.join(app_img_path, "repo"))
        with open(os.path.join(app_img_path, "Dockerfile"), 'a+') as app:

            if "requirements" in self._json:
                app.write("ADD {0} requirements.txt\n".format(self._json["requirements"]))
                app.write("RUN pip install -r requirements.txt\n")
                app.write("\n")

            if "config_scripts" in self._json:
                for script_path in self._json["config_scripts"]:
                    with open(script_path, 'r') as script:
                        for line in script.readlines():
                            app.write("RUN {0}\n".format(line))
                        app.write("\n")

            if "dockerfile" in self._json:
                    dockerfile_path = self._json["dockerfile"]
                    with open(dockerfile_path, 'r') as dockerfile:
                        for line in dockerfile.readlines():
                            app.write(line)
                        app.write("\n")

            # add the notebooks to the app image and set the default command
            nb_img_path = os.path.join(build_path, "add_notebooks")
            with open(os.path.join(nb_img_path, "Dockerfile"), 'r') as nb_img:
                for line in nb_img.readlines():
                    app.write(line)
                app.write("\n")

        # build the app image
        try:
            app_img = app_img_path
            image_name = DOCKER_USER + "/" + self.name
            subprocess.check_call(['docker', 'build', '-t', image_name, app_img])
            subprocess.check_call(['docker', 'push', image_name])
        except subprocess.CalledProcessError as e:
            print("Could not build the app image: {0}".format(self.name))
            success = False

        if success:
            print("Successfully built app: {0}".format(self.name))

    def deploy(self, mode):
        success = True

        # clean up the old deployment
        deploy_path = os.path.join(self.path, "deploy")
        if os.path.isdir(deploy_path):
            shutil.rmtree(deploy_path)
            os.mkdir(deploy_path)

        modules = self._get_modules()
        app_params = self._get_app_params()

        # insert the notebooks container into the pod.json template
        with open(os.path.join(deploy_path, "notebook.json"), 'w+') as nb_file:
            nb_string = fill_template_string(templates["notebook.json"], app_params)
            nb_file.write(nb_string)

        # write deployment files for every module (by passing app parameters down to each module)
        for module in modules:
            success = module.deploy(mode, deploy_path, app_params.copy())

        # use the cluster manager to deploy each file in the deploy/ folder
        ClusterManager.get_instance().deploy_app(deploy_path)

        if success:
            app_id = app_params["app.id"]
            print("Successfully deployed app {0} in {1} mode with ID {2}".format(self.name, mode, app_id))
        else:
            print("Failed to deploy app {0} in {1} mode.".format(self.name, mode))

    def destroy(self):
        pass


class Module(object):

    index = ModuleIndex.get_index(ROOT)

    @staticmethod
    def get_module(name=None, version=None):
        modules = Module.index.find_modules()
        if not name and not version:
            return [Module(m) for m in modules.values()]
        if not name or not version:
            raise ValueError("must specify both name and version or neither")
        full_name = name + "-" + version
        if full_name not in modules:
            raise ValueError("module {0} not found.".format(full_name))
        return Module(modules[full_name])

    def __init__(self, meta):
        self._json = meta["module"]
        self.path = meta["path"]
        self.name = meta["name"]
        self.version = meta["version"]
        self.last_build = meta.get("last_build")
        self.images = self._json.get("images")
        self.parameters = self._json.get("parameters")

    @memoized_property
    def deployments(self):
        deps_path = os.path.join(self.path, "deployments")
        deps = {}
        for dep in os.listdir(deps_path):
            with open(os.path.join(deps_path, dep)) as df:
                deps[dep] = json.load(df)
        return deps

    @memoized_property
    def components(self):
        comps_path = os.path.join(self.path, "components")
        comps = {}
        for comp in os.listdir(comps_path):
            with open(os.path.join(comps_path, comp)) as cf:
                comps[comp] = json.load(cf)
        return comps

    @property
    def full_name(self):
        return self.name + "-" + self.version

    def build(self):
        # only initiate the build if the current spec is different than the last spec built
        if self._json != self.last_build:
            success = True

            # clean up the old build
            build_path = os.path.join(self.path, "build")
            if os.path.isdir(build_path):
                shutil.rmtree(build_path)
                os.mkdir(build_path)

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
                    image_name = DOCKER_USER + "/" + self.full_name + "-" + image["name"]
                    image_path = os.path.join(build_path, "images", image["name"])
                    subprocess.check_call(['docker', 'build', '-t', image_name, image_path])
                    subprocess.check_call(['docker', 'push', image_name])
                except subprocess.CalledProcessError as e:
                    success = False

            if success:
                print("Successfully build {0}".format(self.full_name))
                # write latest build parameters
                self.index.save_module(self)
            else:
                print("Failed to build {0}".format(self.full_name))
        else:
            print("Image {0} not changed since last build. Not rebuilding.".format(self.full_name))

    def deploy(self, mode, deploy_path, app_params):
        """
        Called from within App.deploy
        """
        success = True

        deps = self.deployments
        if mode not in deps:
            raise Exception("module {0} does not support {1} deployment"\
                            .format(module.full_name, mode))

        dep_json = deps[mode]
        comps = module.components

        # load all the template strings
        # TODO this could be more efficient
        templates_path = os.path.join(ROOT, "templates")
        template_names = ["pod.json", "notebook.json", "replicated.json", "service.json"]
        templates = {}
        for name in template_names:
            with open(os.path.join(templates_path, name), 'r') as tf:
                templates[name] = tf.read()

        for comp in dep_json["components"]:
            comp_name = comp["name"]
            comp_type = comp["type"]
            comp_json = comps[comp_name + ".json"]

            final_params = app_params
            final_params.update(namespace_params("module", module.parameters.copy()))
            final_params.update(namespace_params("component", comp.get("parameters", {})))

            filled_comp = fill_template_string(comp, final_params)
            container = {
                "containers": filled_comp
            }
            filled_template = fill_template_string(templates[comp_type + ".json"], container)

            with open(os.path.join(deploy_path, self.name + "-" + comp_type + ".json"), "w+") as df:
                df.write(filled_template)

        return success

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
    modules = Module.get_module(name=args.name)
    if isinstance(modules, list):
        for m in modules:
            m.build()
    elif module:
        module.build()
    else:
        print("Module {0} not found".format(module))

def build_app(args):
    apps = App.get_app(name=args.name)
    if isinstance(apps, list):
        for app in apps:
            app.build()
    elif isinstance(apps, App):
        apps.build()
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

    if args.subcmd == "modules":
        list_modules()
    elif args.subcmd == "apps":
        list_apps()

def list_modules():
    modules = Module.get_module()
    print "Available modules:"
    for module in modules:
        print(" {0}".format(module.full_name))

def list_apps():
    apps = App.get_app()
    print "Available apps:"
    for app in apps:
        print(" {0} - last built: {1}".format(app.name, app.build_time))

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
        deploy_app(args)
    elif args.subcmd == "app":
        list_apps()

def deploy_app(args):
    app = App.get_app(name=args.name)
    if app:
        app.deploy(mode=args.mode)
    else:
        print("App {0} not found".format(app))

def _deploy_subparser(parser):
    p = parser.add_parser("deploy", description="Deploy applications")
    s = p.add_subparsers(dest="subcmd")

    app = s.add_parser("app")
    app.add_argument("name", help="Name of app to deply", type=str)
    app.add_argument("mode", help="Deployment mode (i.e. 'single-mode', 'multi-node',...)" , type=str)

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
Cluster section
"""


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

