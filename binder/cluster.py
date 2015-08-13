import json
import os
import re
import shutil
import subprocess
import time
import requests

from memoized_property import memoized_property

from binder.settings import ROOT, DOCKER_USER
from binder.utils import fill_template_string


class ClusterManager(object):

    # the singleton manager
    manager = None

    @staticmethod
    def get_instance():
        if not ClusterManager.manager:
            ClusterManager.manager = KubernetesManager()
        return ClusterManager.manager

    def start(self, num_minions=3):
        pass

    def stop(self):
        pass

    def destroy(self):
        pass

    def deploy_app(self, app_id, app_dir):
        """
        Deploys an app on the cluster. Returns the IP/port combination for the notebook server
        """
        pass

    def destroy_app(self, app_id):
        pass

    def list_apps(self):
        pass


class KubernetesManager(ClusterManager):

    def __init__(self):
        # set when the cluster is launched
        self.provider = None

    @memoized_property
    def kubernetes_home(self):
        try:
            cmd = ["which", "kubectl.sh"]
            output = subprocess.check_output(cmd)
            return output.split("/cluster/kubectl.sh")[0]
        except subprocess.CalledProcessError as e:
            print("Could not get Kubernetes home: {}".format(e))
            return None

    def _generate_auth_token(self):
        return str(hash(time.time()))

    def _create(self, filename, namespace=None):
        success = True
        try:
            cmd = ["kubectl.sh", "create", "-f", filename]
            if namespace:
                cmd.append('--namespace={0}'.format(namespace))
            subprocess.check_call(cmd)
        except subprocess.CalledProcessError as e:
            success = False
        return success

    def _get_proxy_url(self):
        try:
            cmd = ["kubectl.sh", "describe", "service", "proxy-registration"]
            output = subprocess.check_output(cmd)
            ip_re = re.compile("LoadBalancer Ingress:(?P<ip>.*)\n")
            m = ip_re.search(output)
            if not m:
                print("Could not extract IP from service description")
                return None
            return m.group("ip").strip()
        except subprocess.CalledProcessError as e:
            return None

    def _get_pod_ip(self, app_id):
        try:
            cmd = ["kubectl.sh", "describe", "pod", "notebook-server", "--namespace={}".format(app_id)]
            output = subprocess.check_output(cmd)
            ip_re = re.compile("IP:(?P<ip>.*)\n")
            m = ip_re.search(output)
            if not m:
                print("Could not extract IP from pod description")
                return None
            return m.group("ip").strip()
        except subprocess.CalledProcessError as e:
            return None

    def _launch_proxy_server(self, token):

        # TODO the following chunk of code is reused in App.deploy (should be abstracted away)
        proxy_path = os.path.join(ROOT, "proxy")

         # clean up the old deployment
        deploy_path = os.path.join(proxy_path, "deploy")
        if os.path.isdir(deploy_path):
            shutil.rmtree(deploy_path)
        os.mkdir(deploy_path)

        params = {"token": token}

        # load all the template strings
        templates_path = os.path.join(proxy_path, "deployment")
        template_names = os.listdir(templates_path)
        templates = {}
        for name in template_names:
            with open(os.path.join(templates_path, name), 'r') as tf:
                templates[name] = tf.read()

        # insert the notebooks container into the pod.json template
        for name in template_names:
            with open(os.path.join(deploy_path, name), 'w+') as p_file:
                p_string = fill_template_string(templates[name], params)
                p_file.write(p_string)
            # launch each component
            subprocess.check_call(["kubectl.sh", "create", "-f", os.path.join(deploy_path, name)])

    def _get_proxy_info(self):
        with open(os.path.join(ROOT, ".proxy_info"), "r") as proxy_file:
            raw_host, raw_token = proxy_file.readlines()
            return "http://" + raw_host.strip() + "/api/routes", raw_token.strip()

    def _write_proxy_info(self, url, token):
        with open(os.path.join(ROOT, ".proxy_info"), "w+") as proxy_file:
            proxy_file.write("{}\n".format(url))
            proxy_file.write("{}\n".format(token))

    def _register_proxy_route(self, app_id):
        num_retries = 20
        pause = 5
        for i in range(num_retries):
            # TODO should the notebook port be a parameter?
            ip = self._get_pod_ip(app_id)
            if ip:
                base_url, token = self._get_proxy_info()
                body = {'target': "http://" + ip + ":8888"}
                h = {"Authorization": "token {}".format(token)}
                proxy_url = base_url + "/" + app_id
                print("body: {}, headers: {}, proxy_url: {}".format(body, h, proxy_url))
                r = requests.post(proxy_url, data=json.dumps(body), headers=h)
                if r.status_code == 201:
                    print("Proxying {} to {}".format(proxy_url, ip + ":8888"))
                    return True
                else:
                    raise Exception("could not register route with proxy server")
            print("App not yet assigned an IP address. Waiting for {} seconds...".format(pause))
            time.sleep(pause)

        return False

    def _preload_base_image(self):

        if self.provider == 'gce':

            # get zone info
            zone = os.environ.get("KUBE_GCE_ZONE")
            if not zone:
                zone_re = re.compile("ZONE\=\$\{KUBE_GCE_ZONE:\-(?P<zone>.*)\}")
                with open(os.path.join(self.kubernetes_home, "cluster/gce/config-default.sh"), 'r') as f:
                    m = zone_re.search(f.read())
                    if m:
                        zone = m.group("zone")
                    else:
                        print("zone could not be determined")
            if not zone:
                return False

            try:
                nodes_cmd = ["kubectl.sh", "get", "nodes"]
                output = subprocess.check_output(nodes_cmd)
                for line in output.split('\n')[1:]:
                    node_name = line.split()[0]
                    docker_cmd = "sudo docker pull {}/binder-base".format(DOCKER_USER)
                    cmd = ["gcloud", "compute", "ssh", node_name, "--zone", zone,
                           "--command", "'{}'".format(docker_cmd)]
                    subprocess.check_call(cmd)
                    return True
            except subprocess.CalledProcessError as e:
                print("Could not preload the base image on the workers")
                return False

        elif self.provider == 'aws':
            # TODO support aws
            pass

        else:
            print("Only aws and gce providers are currently supported")
            return False

    def start(self, num_minions=3, provider="gce"):
        self.provider = provider
        success = True
        try:
            # start the cluster
            os.environ["NUM_MINIONS"] = str(num_minions)
            os.environ["KUBERNETES_PROVIDER"] = provider
            subprocess.check_call(['kube-up.sh'])

            # generate an auth token and launch the proxy server
            token = self._generate_auth_token()
            self._launch_proxy_server(token)
            num_retries = 5
            for i in range(num_retries):
                print("Sleeping for 20s before getting proxy URL")
                time.sleep(20)
                proxy_url = self._get_proxy_url()
                if proxy_url:
                    print("proxy_url: {}".format(proxy_url))
                    # record the proxy url and auth token
                    self._write_proxy_info(proxy_url, token)
            if not proxy_url:
                success = False
                print("Could not obtain the proxy server's URL. Cluster launch unsuccessful")

            # preload the generic base image onto all the workers
            success = success and self._preload_base_image()

        except subprocess.CalledProcessError as e:
            success = False

        if success:
            print("Started Kubernetes cluster successfully")
        else:
            print("Could not launch the Kubernetes cluster")
        return success

    def stop(self, provider="gce"):
        try:
            os.environ["KUBERNETES_PROVIDER"] = provider
            subprocess.check_call(['kube-down.sh'])
        except subprocess.CalledProcessError as e:
            print("Could not destroy the Kubernetes cluster")

    def destroy_app(self, app_id):
        pass

    def list_apps(self):
        pass

    def deploy_app(self, app_id, app_dir):
        success = True

        # first create a namespace for the app
        success = self._create(os.path.join(app_dir, "namespace.json"))

        # now launch all other components in the new namespace
        for f in os.listdir(app_dir):
            if f != "namespace.json":
                path = os.path.join(app_dir, f)
                success = self._create(path, namespace=app_id)
                if not success:
                    print("Could not deploy {0} on Kubernetes cluster".format(path))

        # create a route in the proxy
        success = self._register_proxy_route(app_id)

        return success