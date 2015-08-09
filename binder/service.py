import json
import os
import shutil
import subprocess
from memoized_property import memoized_property
from binder.pod_creator import ROOT, fill_template, DOCKER_USER, namespace_params, fill_template_string
from binder.indices import ServiceIndex


class Service(object):

    index = ServiceIndex.get_index(ROOT)

    @staticmethod
    def get_service(name=None, version=None):
        services = Service.index.find_services()
        if not name and not version:
            return [Service(s) for s in services.values()]
        if not name or not version:
            raise ValueError("must specify both name and version or neither")
        full_name = name + "-" + version
        if full_name not in services:
            raise ValueError("service {0} not found.".format(full_name))
        return Service(services[full_name])

    def __init__(self, meta):
        self._json = meta["service"]
        self.path = meta["path"]
        self.name = meta["name"]
        self.version = meta["version"]
        self.last_build = meta.get("last_build")
        self.images = self._json.get("images")
        self.parameters = self._json.get("parameters", {})

    @memoized_property
    def deployments(self):
        deps_path = os.path.join(self.path, "deployments")
        deps = {}
        for dep in os.listdir(deps_path):
            with open(os.path.join(deps_path, dep)) as df:
                deps[dep.split('.')[0]] = df.read()
        return deps

    @memoized_property
    def components(self):
        comps_path = os.path.join(self.path, "components")
        comps = {}
        for comp in os.listdir(comps_path):
            with open(os.path.join(comps_path, comp)) as cf:
                comps[comp] = cf.read()
        return comps

    @memoized_property
    def client(self):
        filename = self._json.get("client")
        if not filename:
            return None
        path = os.path.join(self.path, filename)
        with open(path, 'r') as client_file:
            return client_file.read()

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
                self.index.save_service(self)
            else:
                print("Failed to build {0}".format(self.full_name))
        else:
            print("Image {0} not changed since last build. Not rebuilding.".format(self.full_name))

    def deploy(self, mode, deploy_path, app, templates):
        """
        Called from within App.deploy
        """
        success = True

        app_params = app.get_app_params().copy()

        deps = self.deployments
        if mode not in deps:
            raise Exception("service {0} does not support {1} deployment"\
                            .format(self.full_name, mode))

        service_params = app_params
        service_params.update(namespace_params("service", self.parameters.copy()))
        dep_json = json.loads(fill_template_string(deps[mode], service_params))

        comps = self.components

        for comp in dep_json["components"]:
            comp_name = comp["name"]
            for deployment in comp["deployments"]:
                dep_type = deployment["type"]

                dep_params = deployment.get("parameters", {}).copy()
                dep_params.update(comp.get("parameters", {}))
                # TODO: perhaps this should be done in a cleaner way?
                dep_params["name"] = comp_name
                dep_params["image_name"] = DOCKER_USER + "/" + self.full_name + "-" + comp_name

                final_params = service_params.copy()
                final_params.update(namespace_params("component", dep_params))
                print("final_params: {0}".format(final_params))

                filled_comp = fill_template_string(comps[comp_name + ".json"], final_params)

                final_params["containers"] = filled_comp
                filled_template = fill_template_string(templates[dep_type + ".json"], final_params)

                with open(os.path.join(deploy_path, comp_name + "-" + dep_type + ".json")\
                        , "w+") as df:
                    df.write(filled_template)

        return success

    def to_json(self):
        return self._json