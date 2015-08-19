import json
import os
import re
import shutil
import subprocess
import time
import requests
from urlparse import urljoin
from datetime import datetime, timedelta
from crontab import CronTab

from memoized_property import memoized_property
from multiprocess import Pool

from binder.settings import ROOT, REGISTRY_NAME, DOCKER_HUB_USER, APP_CRON_PERIOD
from binder.utils import fill_template_string, get_env_string


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

    pool = Pool(5)

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
            print("Could not deploy specification: {0} on Kubernetes cluster: {1}".format(path, e))
            success = False
        return success

    def __get_service_url(self, service_name):
        try:
            cmd = ["kubectl.sh", "describe", "service", service_name]
            output = subprocess.check_output(cmd)
            ip_re = re.compile("LoadBalancer Ingress:(?P<ip>.*)\n")
            m = ip_re.search(output)
            if not m:
                print("Could not extract IP from service description")
                return None
            return m.group("ip").strip()
        except subprocess.CalledProcessError as e:
            return None

    def _get_proxy_url(self):
        return self.__get_service_url("proxy-registration")

    def _get_registry_url(self):
        return self.__get_service_url("registry")

    def _get_lookup_url(self):
        return self.__get_service_url("proxy-lookup")

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

    def _launch_registry_server(self):
        registry_path = os.path.join(ROOT, "registry")

        for name in os.listdir(registry_path):
            self._create(os.path.join(registry_path, name))

        print("Sleeping for 10 seconds so registry launch can complete...")
        time.sleep(10)

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
            self._create(os.path.join(deploy_path, name))

    def _read_proxy_info(self):
        with open(os.path.join(ROOT, ".proxy_info"), "r") as proxy_file:
            raw_host, raw_token = proxy_file.readlines()
            return "http://" + raw_host.strip() + "/api/routes", raw_token.strip()

    def _write_proxy_info(self, url, token):
        with open(os.path.join(ROOT, ".proxy_info"), "w+") as proxy_file:
            proxy_file.write("{}\n".format(url))
            proxy_file.write("{}\n".format(token))

    def _read_registry_url(self):
        with open(os.path.join(ROOT, ".registry_info"), "r") as registry_file:
            url = registry_file.readlines()[0]
            return url

    def _write_registry_url(self, url):
        with open(os.path.join(ROOT, ".registry_info"), "w+") as registry_file:
            registry_file.write("{}\n".format(url))

    def _get_inactive_routes(self, min_inactive):
        now = datetime.utcnow()
        threshold = (now - timedelta(minutes=min_inactive)).isoformat()

        base_url, token = self._read_proxy_info()
        h = {"Authorization": "token {}".format(token)}
        proxy_url = base_url + "?inactive_since={}".format(threshold)
        print("proxy_url: {}".format(proxy_url))
        try:
            r = requests.get(proxy_url, headers=h)
            if r.status_code == 200:
                routes = r.json().keys()
                return map(lambda r: r[1:], routes)
        except requests.exceptions.ConnectionError:
            print("Could not get all routes inactive for {} minutes".format(min_inactive))
        return None

    def _remove_proxy_route(self, app_id):
        base_url, token = self._read_proxy_info()
        h = {"Authorization": "token {}".format(token)}
        proxy_url = base_url + "/" + app_id
        try:
            r = requests.delete(proxy_url, headers=h)
            if r.status_code == 204:
                print("Removed proxy route for {}".format(app_id))
                return True
        except requests.exceptions.ConnectionError:
            print("Could not remove proxy route for {}".format(app_id))
        return False

    def _register_proxy_route(self, app_id):
        num_retries = 30
        pause = 1
        for i in range(num_retries):
            # TODO should the notebook port be a parameter?
            ip = self._get_pod_ip(app_id)
            if ip:
                base_url, token = self._read_proxy_info()
                body = {'target': "http://" + ip + ":8888"}
                h = {"Authorization": "token {}".format(token)}
                proxy_url = base_url + "/" + app_id
                print("body: {}, headers: {}, proxy_url: {}".format(body, h, proxy_url))
                try:
                    r = requests.post(proxy_url, data=json.dumps(body), headers=h)
                    if r.status_code == 201:
                        print("Proxying {} to {}".format(proxy_url, ip + ":8888"))
                        return True
                    else:
                        raise Exception("could not register route with proxy server")
                except requests.exceptions.ConnectionError:
                    pass
            print("App not yet assigned an IP address. Waiting for {} seconds...".format(pause))
            time.sleep(pause)

        return False

    def preload_image(self, image_name):

        provider = os.environ["KUBERNETES_PROVIDER"]

        if provider == 'gce':

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

            nodes_cmd = ["kubectl.sh", "get", "nodes"]
            output = subprocess.check_output(nodes_cmd)
            nodes = output.split("\n")[1:]
           
            def preload(node):
                split = node.split()
                if len(split) > 0:
                    node_name = split[0]
                    if node_name != "kubernetes-master":
                        print("Preloading {0} onto {1}...".format(image_name, node_name))
                        docker_cmd = "sudo docker pull {0}/{1}".format(REGISTRY_NAME, image_name)
                        cmd = ["gcloud", "compute", "ssh", node_name, "--zone", zone,
                               "--command", "{}".format(docker_cmd)]
                        return subprocess.Popen(cmd)
                return None
            
            procs = [preload(node) for node in nodes]
            print("Waiting for preloading to finish...")
            for proc in procs:
                if proc:
                    proc.wait()
            print("Preloaded image {} onto all nodes".format(image_name))
            return True

        elif provider == 'aws':
            # TODO support aws
            pass

        else:
            print("Only aws and gce providers are currently supported")
            return False

    def _start_proxy_server(self):
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
                break
        if not proxy_url:
            print("Could not obtain the proxy server's URL. Cluster launch unsuccessful")
            return False

    def _start_registry_server(self):
        # TODO remove duplicated code here
        self._launch_registry_server()
        num_retries = 5
        for i in range(num_retries):
            print("Sleeping for 20s before getting registry URL")
            time.sleep(20)
            registry_url = self._get_registry_url()
            if registry_url:
                print("registry_url: {}".format(registry_url))
                # record the registry url 
                self._write_registry_url(registry_url)
                break
        if not registry_url:
            print("Could not obtain the registry server's URL. Cluster launch unsuccessful")
            return False

    def _preload_registry_server(self):
        try:
            subprocess.check_call(["docker", "pull", "{}/binder-base".format(DOCKER_HUB_USER)])
            subprocess.check_call(["docker", "tag", "{}/binder-base".format(DOCKER_HUB_USER),
                "{}/binder-base".format(REGISTRY_NAME)])
            subprocess.check_call(["docker", "push", "{}/binder-base".format(REGISTRY_NAME)])
            return True
        except subprocess.CalledProcessError as e:
            print("Could not preload registry server with binder-base image: {}".format(e))
            return False

    def start(self, num_minions=3, provider="gce"):
        success = True
        try:
            # start the cluster
            os.environ["NUM_MINIONS"] = str(num_minions)
            os.environ["KUBERNETES_PROVIDER"] = provider
            subprocess.check_call(['kube-up.sh'])

            # generate an auth token and launch the proxy server
            print("Launching proxy server...")
            self._start_proxy_server()

            # launch the private Docker registry
            print("Launching private Docker registry...")
            self._start_registry_server()
            print("Preloading registry server with binder-base image...")
            self._preload_registry_server()

            # preload the generic base image onto all the workers
            print("Preloading binder-base image onto all nodes...")
            success = success and self.preload_image("binder-base")

            # start the inactive app removal cron job
            cron = CronTab()
            cmd = " ".join([get_env_string(), os.path.join(ROOT, "util", "stop-inactive-apps"),
                            "&>/tmp/binder-cron"])
            job = cron.new(cmd, comment="binder-stop")
            job.minute.every(APP_CRON_PERIOD)
            job.enable(True)
            cron.write_to_user(user=True)

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

            # start the inactive app removal cron job
            cron = CronTab()
            jobs = cron.find_comment("binder-stop")
            for job in jobs:
                job.enable(False)
                cron.remove(job)
            cron.write_to_user(user=True)

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
                success = success and self._create(path, namespace=app_id)
                if not success:
                    print("Could not deploy {0} on Kubernetes cluster".format(path))

        # create a route in the proxy
        success = success and self._register_proxy_route(app_id)
        if not success:
            return None

        lookup_url = "http://" + self._get_lookup_url()
        app_url = urljoin(lookup_url, app_id)
        print("Access app at: \n   {}".format(app_url))
        return app_url

    def stop_app(self, app_id):
        try:
            stop_cmd = ["kubectl.sh", "stop", "pods,services,replicationControllers", "--all",
                   "--namespace={}".format(app_id)]
            cleanup_cmd = ["kubectl.sh", "delete", "namespace", app_id]
            subprocess.check_call(stop_cmd)
            subprocess.check_call(cleanup_cmd)
            self._remove_proxy_route(app_id)
            print("Stopped app {}".format(app_id))
        except subprocess.CalledProcessError as e:
            print("Could not stop app {}".format(app_id))

    def stop_inactive_apps(self, min_inactive):
        routes = self._get_inactive_routes(min_inactive)
        if not routes:
            print("No inactive apps to stop")
            return
        for app_id in routes:
            print("Stopping inactive app {}".format(app_id))
            self.stop_app(app_id)



