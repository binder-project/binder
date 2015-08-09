import os
import shutil
import subprocess
from memoized_property import memoized_property
from binder.settings import ROOT, DOCKER_USER
from binder.utils import namespace_params, fill_template, fill_template_string
from binder.cluster import ClusterManager
from binder.indices import AppIndex
from binder.service import Service


class App(object):

    index = AppIndex.get_index(ROOT)

    @staticmethod
    def get_app(name=None):
        apps = App.index.find_apps()
        print "name: {0}, apps: {1}".format(name, str(apps))
        if not name:
            return [App(a) for a in apps.values()]
        return App(apps.get(name))

    def __init__(self, meta):
        self._json = meta["app"]
        self.path = meta["path"]
        self.name = self._json.get("name")
        self.service_names = self._json.get("services")
        self.config_scripts = self._json.get("config_scripts")
        self.requirements = self._json.get("requirements")
        self.repo = os.path.join(self.path, self._json.get("root"))

        self.app_id = self._get_deployment_id()

        self.build_time = 0

    def get_app_params(self):
        # TODO some of these should be moved into some sort of a Defaults class (config file?)
        return namespace_params("app", {
                "name": self.name,
                "id": self.app_id,
                "notebooks_image": DOCKER_USER + "/" + self.name,
                "notebooks_port": 8888
        })

    def _get_deployment_id(self):
        import time
        return str(hash(time.time()))

    @memoized_property
    def services(self):
        return [Service.get_service(s_json["name"], s_json["version"]) for s_json in self.service_names]

    def build(self):
        success = True

        # clean up the old build
        build_path = os.path.join(self.path, "build")
        if os.path.isdir(build_path):
            shutil.rmtree(build_path)
            os.mkdir(build_path)

        # ensure that the service dependencies are all build
        print "Building service dependencies..."
        for service in self.services:
            service.build()

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

            if "config_scripts" in self._json:
                for script_path in self._json["config_scripts"]:
                    with open(os.path.join(app_img_path, script_path), 'r') as script:
                        app.write(script.read())
                        app.write("\n")

            if "requirements" in self._json:
                app.write("ADD {0} requirements.txt\n".format(self._json["requirements"]))
                app.write("RUN pip install -r requirements.txt\n")
                app.write("\n")

            # if any services have client code, insert that now
            for service in self.services:
                client = service.client if service.client else ""
                app.write("# {} client\n".format(service.name))
                app.write(client)
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

        services = self.services
        app_params = self.get_app_params()

        # load all the template strings
        templates_path = os.path.join(ROOT, "templates")
        template_names = ["namespace.json", "pod.json", "service-pod.json", "notebook.json",
                          "controller.json", "service.json"]
        templates = {}
        for name in template_names:
            with open(os.path.join(templates_path, name), 'r') as tf:
                templates[name] = tf.read()

        # insert the notebooks container into the pod.json template
        with open(os.path.join(deploy_path, "notebook.json"), 'w+') as nb_file:
            nb_string = fill_template_string(templates["notebook.json"], app_params)
            nb_file.write(nb_string)

        # insert the namespace file into the deployment folder
        with open(os.path.join(deploy_path, "namespace.json"), 'w+') as ns_file:
            ns_string = fill_template_string(templates["namespace.json"], app_params)
            ns_file.write(ns_string)

        # write deployment files for every service (by passing app parameters down to each service)
        for service in services:
            deployed_service = service.deploy(mode, deploy_path, self, templates)
            if not deployed_service:
                success = False

        # use the cluster manager to deploy each file in the deploy/ folder
        deployed_app = ClusterManager.get_instance().deploy_app(self.app_id, deploy_path)
        if not deployed_app:
            success = False

        if success:
            app_id = app_params["app.id"]
            print("Successfully deployed app {0} in {1} mode with ID {2}".format(self.name, mode, app_id))
        else:
            print("Failed to deploy app {0} in {1} mode.".format(self.name, mode))

    def destroy(self):
        pass