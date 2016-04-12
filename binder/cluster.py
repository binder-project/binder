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

from binder.settings import MainSettings, MonitoringSettings
from binder.utils import fill_template_string, get_env_string
from binder.log import *


class ClusterManager(object):

    TAG = "ClusterManager"
    CLUSTER_HOST = "app.mybinder.org:80"

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

    def list_running_apps(self):
        pass

    def get_total_capacity(self):
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
    
    TAG = "KubernetesManager"

    pool = Pool(5)

    @memoized_property
    def kubernetes_home(self):
        try:
            cmd = ["which", "kubectl.sh"]
            output = subprocess.check_output(cmd)
            return output.split("/cluster/kubectl.sh")[0]
        except subprocess.CalledProcessError as e:
            error_log(self.TAG, "Could not get Kubernetes home: {}".format(e))
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
            msg = "Could not deploy specification: {0} on Kubernetes cluster: {1}".format(filename, e)
            error_log(self.TAG, msg)
            success = False
        return success

    def __get_service_url(self, service_name):
        try:
            cmd = ["kubectl.sh", "describe", "service", service_name]
            output = subprocess.check_output(cmd)
            ip_re = re.compile("LoadBalancer Ingress:(?P<ip>.*)\n")
            m = ip_re.search(output)
            if not m:
                error_log(self.TAG, "Could not extract IP from service description")
                return None
            return m.group("ip").strip()
        except subprocess.CalledProcessError as e:
            return None

    def _get_proxy_url(self):
        return self.__get_service_url("proxy-registration")

    def _get_registry_url(self):
        return self.__get_service_url("registry")

    def _get_lookup_url(self):
        #return self.__get_service_url("proxy-lookup")
        return ClusterManager.CLUSTER_HOST

    def _get_pod_ip(self, app_id):
        try:
            cmd = ["kubectl.sh", "describe", "pod", "notebook-server", "--namespace={}".format(app_id)]
            output = subprocess.check_output(cmd)
            ip_re = re.compile("IP:(?P<ip>.*)\n")
            ready_re = re.compile("State:\s+(?P<ready>.*)")
            m = ip_re.search(output)
            if not m:
                info_log(self.TAG, "Could not extract IP from pod description")
                return None
            return m.group("ip").strip()

            # TODO the following code makes the above check safer (will prevent proxy errors) but is too slow
            ready = ready_re.search(output)
            if not ready:
                warning_log(self.TAG, "Extracted the pod IP, but the notebook container is not ready")
                return None
            else:
                status = ready.group("ready").lower().strip()
                debug_log(self.TAG, "status: {}".format(status))
                if status != "running":
                    info_log(self.TAG, "Extracted the pod IP, but the notebook container is not ready")
                    return None

        except subprocess.CalledProcessError as e:
            return None

    def _launch_registry_server(self):
        registry_path = os.path.join(MainSettings.ROOT, "registry")

        for name in os.listdir(registry_path):
            self._create(os.path.join(registry_path, name))

        info_log(self.TAG, "Sleeping for 10 seconds so registry launch can complete...")
        time.sleep(10)

    def _launch_proxy_server(self, token):

        # TODO the following chunk of code is reused in App.deploy (should be abstracted away)
        proxy_path = os.path.join(MainSettings.ROOT, "proxy")

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
        with open(os.path.join(MainSettings.ROOT, ".proxy_info"), "r") as proxy_file:
            raw_host, raw_token = proxy_file.readlines()
            return "http://" + raw_host.strip() + "/api/routes", raw_token.strip()

    def _write_proxy_info(self, url, token):
        with open(os.path.join(MainSettings.ROOT, ".proxy_info"), "w+") as proxy_file:
            proxy_file.write("{}\n".format(url))
            proxy_file.write("{}\n".format(token))

    def _read_registry_url(self):
        with open(os.path.join(MainSettings.ROOT, ".registry_info"), "r") as registry_file:
            url = registry_file.readlines()[0]
            return url

    def _write_registry_url(self, url):
        with open(os.path.join(MainSettings.ROOT, ".registry_info"), "w+") as registry_file:
            registry_file.write("{}\n".format(url))

    def _get_inactive_routes(self, min_inactive):
        now = datetime.utcnow()
        threshold = (now - timedelta(minutes=min_inactive)).isoformat()

        base_url, token = self._read_proxy_info()
        h = {"Authorization": "token {}".format(token)}
        proxy_url = base_url + "?inactive_since={}".format(threshold)
        debug_log(self.TAG, "proxy_url: {}".format(proxy_url))
        try:
            r = requests.get(proxy_url, headers=h)
            if r.status_code == 200:
                routes = r.json().keys()
                return map(lambda r: r[1:], routes)
        except requests.exceptions.ConnectionError:
            warning_log(self.TAG, "Could not get all routes inactive for {} minutes".format(min_inactive))
        return None

    def _remove_proxy_route(self, app_id):
        base_url, token = self._read_proxy_info()
        h = {"Authorization": "token {}".format(token)}
        proxy_url = base_url + "/" + app_id
        try:
            r = requests.delete(proxy_url, headers=h)
            if r.status_code == 204:
                info_log(self.TAG, "Removed proxy route for {}".format(app_id))
                return True
        except requests.exceptions.ConnectionError:
            error_log(self.TAG, "Could not remove proxy route for {}".format(app_id))
        return False

    def _register_proxy_route(self, app_id):
        num_retries = 30
        pause = 1
        for i in range(num_retries):
            # TODO should the notebook port be a parameter?
            ip = self._get_pod_ip(app_id)
            # TODO this is a stopgap solution for a race condition that should be fixed through other means
            time.sleep(1)
            if ip:
                base_url, token = self._read_proxy_info()
                body = {'target': "http://" + ip + ":8888"}
                h = {"Authorization": "token {}".format(token)}
                proxy_url = base_url + "/" + app_id
                debug_log(self.TAG, "body: {}, headers: {}, proxy_url: {}".format(body, h, proxy_url))
                try:
                    r = requests.post(proxy_url, data=json.dumps(body), headers=h)
                    if r.status_code == 201:
                        info_log(self.TAG, "Proxying {} to {}".format(proxy_url, ip + ":8888"))
                        return True
                    else:
                        raise Exception("could not register route with proxy server")
                except requests.exceptions.ConnectionError:
                    error_log(self.TAG, "could not connect to proxy server")
                    pass
            info_log(self.TAG, "App not yet assigned an IP address. Waiting for {} seconds...".format(pause))
            time.sleep(pause)

        return False

    def get_running_apps(self):
        try:
            proxy_loc = MainSettings.KUBE_PROXY_HOST + ':' + MainSettings.KUBE_PROXY_PORT
            url = urljoin(proxy_loc, "/api/v1/pods")
            r = requests.get(url)
            if r.status_code != 200:
                error_log(self.TAG, "could not get list of running pods")
                return None
            json = r.json()
            if 'items' not in json:
                error_log(self.TAG, "pods api endpoint returning malformed JSON")
                return None
            pod_specs = json['items']
            pods = []
            for pod_spec in pod_specs:
                meta = pod_spec['metadata']
                if meta['namespace'] == 'kube-system' or meta['namespace'] == 'default':
                    continue
                if meta['name'] == 'notebook-server':
                    full_image = pod_spec['spec']['containers'][0]['image']
                    image_name = full_image.split('/')[-1]
                    pods.append((meta['namespace'], image_name))
            return pods
        except ConnectionError as e:
            error_log(self.TAG, e)
            return None

    def _nodes_command(self, func, shell=False):
        provider = os.environ["KUBERNETES_PROVIDER"]

        if isinstance(func, str):
            func_str = func
            def _func(node, zone):
                split = node.split()
                if len(split) > 0:
                    node_name = split[0]
                    if node_name != "kubernetes-master":
                        info_log(self.TAG, "Running {0} on {1}...".format(func, node_name))
                        cmd = ["gcloud", "compute", "ssh", node_name, "--zone", zone,
                               "--command", "{}".format(func_str)]
                        return subprocess.Popen(cmd, shell=shell)
                return None
            func = _func

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
                        error_log(self.TAG, "zone could not be determined")
            if not zone:
                return False

            nodes_cmd = ["kubectl.sh", "get", "nodes"]
            output = subprocess.check_output(nodes_cmd)
            nodes = output.split("\n")[1:]
            
            return [func(node, zone) for node in nodes]          
            
        elif provider == 'aws':
            # TODO support aws
            return []

        else:
            warning_log(self.TAG, "Only aws and gce providers are currently supported")
            return []

    def get_total_capacity(self):
        def _get_capacity(node, zone):
            pod_re = re.compile(".*pods:\s+(?P<pods>\d+)")
            split = node.split()
            if len(split) > 0:
                node_name = split[0]
                cmd = ['kubectl.sh', 'describe', 'node', node_name]
                output_lines = subprocess.check_output(cmd).split('\n')
                match_lines = [pod_re.search(l) for l in output_lines if pod_re.search(l)]
                if match_lines:
                    return int(match_lines[0].group('pods'))
                return 0
            return 0
        caps = self._nodes_command(_get_capacity)
        return sum(caps)
           
    def preload_image(self, image_name):
        def _preload(node, zone):
            split = node.split()
            if len(split) > 0:
                node_name = split[0]
                if node_name != "kubernetes-master":
                    info_log(self.TAG, "Preloading {0} onto {1}...".format(image_name, node_name))
                    docker_cmd = "sudo gcloud docker pull {0}/{1}".format(MainSettings.REGISTRY_NAME, image_name)
                    cmd = ["gcloud", "compute", "ssh", node_name, "--zone", zone,
                           "--command", "{}".format(docker_cmd)]
                    return subprocess.Popen(cmd)
            return None
        procs = self._nodes_command(_preload)
        info_log(self.TAG, "Waiting for preloading to finish...")
        for proc in procs:
            if proc:
                proc.wait()
        info_log(self.TAG, "Preloaded image {} onto all nodes".format(image_name))
        return True

    def _start_proxy_server(self):
        token = self._generate_auth_token()
        self._launch_proxy_server(token)
        num_retries = 5
        for i in range(num_retries):
            debug_log(self.TAG, "Sleeping for 20s before getting proxy URL")
            time.sleep(20)
            proxy_url = self._get_proxy_url()
            if proxy_url:
                debug_log(self.TAG, "proxy_url: {}".format(proxy_url))
                # record the proxy url and auth token
                self._write_proxy_info(proxy_url, token)
                break
        if not proxy_url:
            error_log(self.TAG, "Could not obtain the proxy server's URL. Cluster launch unsuccessful")
            return False

    def _start_registry_server(self):
        # TODO remove duplicated code here
        self._launch_registry_server()
        num_retries = 5
        for i in range(num_retries):
            debug_log(self.TAG, "Sleeping for 20s before getting registry URL")
            time.sleep(20)
            registry_url = self._get_registry_url()
            if registry_url:
                debug_log(self.TAG, "registry_url: {}".format(registry_url))
                # record the registry url 
                self._write_registry_url(registry_url)
                break
        if not registry_url:
            error_log(self.TAG, "Could not obtain the registry server's URL. Cluster launch unsuccessful")
            return False

    def _preload_registry_server(self):
        try:
            subprocess.check_call(["docker", "pull", "{}/binder-base".format(MainSettings.DOCKER_HUB_USER)])
            subprocess.check_call(["docker", "tag", "{}/binder-base".format(MainSettings.DOCKER_HUB_USER),
                "{}/binder-base".format(MainSettings.REGISTRY_NAME)])
            subprocess.check_call(["docker", "push", "{}/binder-base".format(MainSettings.REGISTRY_NAME)])
            return True
        except subprocess.CalledProcessError as e:
            error_log(self.TAG, "Could not preload registry server with binder-base image: {}".format(e))
            return False

    def start(self, num_minions=3, provider="gce"):
        success = True
        try:
            # start the cluster
            os.environ["NUM_MINIONS"] = str(num_minions)
            os.environ["KUBERNETES_PROVIDER"] = provider
            subprocess.check_call(['kube-up.sh'])
        
            # launch binderd
            binderd_proc = subprocess.Popen(["binderd"])
            # sleep just for good measure (modules starting up)
            time.sleep(5)

            # generate an auth token and launch the proxy server
            info_log(self.TAG, "Launching proxy server...")
            self._start_proxy_server()

            # launch the private Docker registry
            info_log(self.TAG, "Launching private Docker registry...")
            self._start_registry_server()
            info_log(self.TAG, "Preloading registry server with binder-base image...")
            self._preload_registry_server()

            # preload the generic base image onto all the workers
            info_log(self.TAG, "Preloading binder-base image onto all nodes...")
            success = success and self.preload_image("binder-base")

            # start the inactive app removal cron job
            cron = CronTab()
            cmd = " ".join([get_env_string(), os.path.join(MainSettings.ROOT, "util", "stop-inactive-apps"),
                            "&>/tmp/binder-cron"])
            job = cron.new(cmd, comment="binder-stop")
            job.minute.every(MonitoringSettings.APP_CRON_PERIOD)
            job.enable(True)
            cron.write_to_user(user=True)

        except subprocess.CalledProcessError as e:
            success = False

        if success:
            info_log(self.TAG, "Started Kubernetes cluster successfully")
        else:
            error_log(self.TAG, "Could not launch the Kubernetes cluster")
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
            error_log(self.TAG, "Could not destroy the Kubernetes cluster")

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
                    error_log(self.TAG, "Could not deploy {0} on Kubernetes cluster".format(path))

        # create a route in the proxy
        success = success and self._register_proxy_route(app_id)
        if not success:
            error_log(self.TAG, "Could not deploy {} on Kubernetes cluster".format(path))
            return None

        lookup_url = self._get_lookup_url()
        app_url = urljoin("https://" + lookup_url, app_id)
        info_log(self.TAG, "Access app at: \n   {}".format(app_url))
        return app_url

    def stop_app(self, app_id):
        if app_id == "kube-system":
            return 
        try:
            self._remove_proxy_route(app_id)
            stop_cmd = ["kubectl.sh", "stop", "pods,services,replicationControllers", "--all",
                   "--namespace={}".format(app_id)]
            cleanup_cmd = ["kubectl.sh", "delete", "namespace", app_id]
            subprocess.check_call(stop_cmd)
            subprocess.check_call(cleanup_cmd)
            info_log(self.TAG, "Stopped app {}".format(app_id))
        except subprocess.CalledProcessError as e:
            error_log(self.TAG, "Could not stop app {}".format(app_id))

    def _stop_apps(self, app_ids):
        if not app_ids:
            info_log(self.TAG, "No apps to stop")
            return
        for app_id in app_ids:
            self.stop_app(app_id)

    def stop_inactive_apps(self, min_inactive):
        routes = self._get_inactive_routes(min_inactive)
        self._stop_apps(routes)

    def stop_all_apps(self):
        app_ids = map(lambda app: app[0], self.get_running_apps())
        self._stop_apps(app_ids)

