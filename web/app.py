import Queue
import json
import signal
import time
import datetime
import threading
from threading import Thread
from concurrent.futures import ThreadPoolExecutor

from tornado import gen, concurrent
from tornado.ioloop import IOLoop, PeriodicCallback
from tornado.web import Application, RequestHandler
from tornado.httpserver import HTTPServer
from tornado.websocket import WebSocketHandler

from binder.service import Service
from binder.app import App
from binder.cluster import ClusterManager
from binder.log import AppLogStreamer, get_app_logs 
from binder.settings import LogSettings

from .builder import Builder

# TODO move settings into a config file
PORT = 8080
NUM_WORKERS = 10
PRELOAD = True
QUEUE_SIZE = 50
ALLOW_ORIGIN = True

build_queue = Queue.Queue(QUEUE_SIZE)

ws_handlers = []

class BinderHandler(RequestHandler):

    def __init__(self, request, application, **kwargs):
        super(BinderHandler, self).__init__(request, application, **kwargs)
        self.executor = ThreadPoolExecutor(max_workers=10)

    def get(self):
        if ALLOW_ORIGIN:
            self.set_header('Access-Control-Allow-Origin', '*')

    @concurrent.run_on_executor
    def _get_app(self, app_name):
        return App.get_app(app_name)

    @concurrent.run_on_executor
    def _get_services(self):
        return Service.get_service()

    @concurrent.run_on_executor
    def _get_apps(self):
        return App.get_app()

    @concurrent.run_on_executor
    def _deploy_app(self, app, mode):
        return app.deploy(mode)

    def post(self):
        if ALLOW_ORIGIN:
            self.set_header('Access-Control-Allow-Origin', '*')

class BuildHandler(BinderHandler):

    def _is_malformed(self, spec):
        # by default, there aren't any required fields in an app specification
        pass

    def _write_build_state(self, app):
        if app.build_state == App.BuildState.BUILDING:
            self.write({"build_status": "building"})
        elif app.build_state == App.BuildState.FAILED:
            self.write({"build_status": "failed"})
        elif app.build_state == App.BuildState.COMPLETED:
             self.write({"build_status": "completed"})
        else:
            self.write({"build_status": "unknown"})


class GithubHandler(BuildHandler):

    def _is_malformed(self, spec):
        # in the GithubHandler, the repo field is inferred from organization/repo
        return "repo" in spec


class GithubStatusHandler(GithubHandler):

    @gen.coroutine
    def get(self, organization, repo):
        super(GithubStatusHandler, self).get()
        app_name = App.make_app_name(organization, repo)
        app = yield self._get_app(app_name)
        if not app:
            self.set_status(404)
            self.write({"error": "app does not exist"})
        else:
            self._write_build_state(app)


class GithubBuildHandler(GithubHandler):

    @gen.coroutine
    def get(self, organization, repo):
        # if the app is still building, return an error. If the app is built, deploy it and return
        # the redirect url
        super(GithubHandler, self).get()
        app_name = App.make_app_name(organization, repo)
        app = yield self._get_app(app_name)
        if app and app.build_state == App.BuildState.COMPLETED:
            redirect_url = yield self._deploy_app(app, "single-node")
            self.write({"redirect_url": redirect_url})
        else:
            self.set_status(404)
            self.write({"error": "no app available to deploy"})

    def post(self, organization, repo):
        # if the spec is properly formed, create/build the app
        super(GithubBuildHandler, self).post()
        print("request.body: {}".format(self.request.body))
        spec = json.loads(self.request.body)
        if self._is_malformed(spec):
            self.set_status(400)
            self.write({"error": "malformed app specification"})
        else:
            try:
                spec["name"] = App.make_app_name(organization, repo).lower()
                spec["repo"] = "https://www.github.com/{0}/{1}".format(organization, repo)
                build_queue.put(spec)
                self.write({"success": "app submitted to build queue"})
            except Queue.Full:
                self.write({"error": "build queue full"})


class OtherSourceHandler(BuildHandler):
    def get(self, app_id):
        pass

    def post(self, app_id):
        pass

class ServicesHandler(BinderHandler):

    @gen.coroutine
    def get(self):
        super(ServicesHandler, self).get()
        services = yield self._get_services()
        self.write({"services": [service.full_name for service in services]})

class AppsHandler(BinderHandler):

    @gen.coroutine
    def get(self):
        super(AppsHandler, self).get()
        apps = yield self._get_apps()
        self.write({"apps": [{"name": app.name, "repo": app.repo_url} for app in apps]})

class RunningAppsHandler(BinderHandler):
    
    @concurrent.run_on_executor
    def _get_running_apps(self):
        cm = ClusterManager.get_instance()
        return cm.get_running_apps()

    @gen.coroutine
    def get(self):
        super(RunningAppsHandler, self).get()
        running_apps = yield self._get_running_apps()
        self.write({"apps": map(lambda app: app[1], running_apps)})
         

class CapacityHandler(BinderHandler):

    POLL_PERIOD = 3600

    cached_capacity = None
    last_poll = None

    @concurrent.run_on_executor
    def _get_capacity(self, cm):
        return cm.get_total_capacity()
    
    @gen.coroutine
    def get(self):
        super(CapacityHandler, self).get()
        cm = ClusterManager.get_instance()
        # don't count the default and kube-system namespaces
        running = len(cm.get_running_apps()) - 3
        if not self.last_poll or not self.cached_capacity or\
                time.time() - self.last_poll > CapacityHandler.POLL_PERIOD:
            capacity = yield self._get_capacity(cm)
            CapacityHandler.cached_capacity = capacity
            CapacityHandler.last_poll = time.time()
        self.write({"capacity": self.cached_capacity, "running": running})

class StaticLogsHandler(BinderHandler):

    @concurrent.run_on_executor
    def _get_app_logs(self, app_name, time_string):
        return get_app_logs(app_name, time_string)

    @gen.coroutine
    def get(self, organization, repo):
        super(StaticLogsHandler, self).get()
        app_name = App.make_app_name(organization, repo)
        app = yield self._get_app(app_name)
        time_string = datetime.datetime.strftime(app.last_build_time, LogSettings.TIME_FORMAT)
        logs = yield self._get_app_logs(app_name, time_string)
        self.write({"logs": logs})
        

class LiveLogsHandler(WebSocketHandler):

    class LogsThread(Thread):
        
        def __init__(self, app_name, handler):
            super(LiveLogsHandler.LogsThread, self).__init__()
            self._app_name = app_name
           
            self._stream = None
            self._handler = handler
            self._stopped = False

        def stop(self):
            self._stopped = True

        def run(self):
            app = App.get_app(self._app_name)
            time_string = datetime.datetime.strftime(app.last_build_time, LogSettings.TIME_FORMAT)
            self._stream = AppLogStreamer(self._app_name, time_string).get_stream()
            while not self._stopped:
                time.sleep(0.10)
                try: 
                    msg = self._stream.next()
                    if msg:
                        IOLoop.instance().add_callback(self._handler.write_message, msg)
                except StopIteration:
                    self.stop()
            ws_handlers.remove(self._handler)
                
    def __init__(self, application, request, **kwargs):
        super(LiveLogsHandler, self).__init__(application, request, **kwargs)
        self._thread = None

    def stop(self):
        if self._thread:
            self._thread.stop()

    def check_origin(self, origin):
        return True

    def open(self, organization, repo):
        super(LiveLogsHandler, self).open()
        print("Opening websocket for {}/{}".format(organization, repo))
        app_name = App.make_app_name(organization, repo)

        ws_handlers.append(self)

        self._thread = LiveLogsHandler.LogsThread(app_name, self)
        self._thread.start()

    def on_message(self, message):
        pass

    def on_close(self):
        super(LiveLogsHandler, self).on_close()
        self.stop()
        if self._thread:
            self._thread.join()

def sig_handler(sig, frame):
    IOLoop.instance().add_callback(shutdown)

def shutdown():
    print("Shutting down...")
    for handler in ws_handlers:
        handler.stop()
    IOLoop.instance().stop()
    builder.stop()

def main():

    application = Application([
        (r"/apps/(?P<organization>.+)/(?P<repo>.+)/status", GithubStatusHandler),
        (r"/apps/(?P<organization>.+)/(?P<repo>.+)/logs/static", StaticLogsHandler),
        (r"/apps/(?P<organization>.+)/(?P<repo>.+)/logs/live", LiveLogsHandler),
        (r"/apps/(?P<organization>.+)/(?P<repo>.+)", GithubBuildHandler),
        (r"/apps/(?P<app_id>.+)", OtherSourceHandler),
        (r"/running", RunningAppsHandler),
        (r"/services", ServicesHandler),
        (r"/apps", AppsHandler),
        (r"/capacity", CapacityHandler)
    ], debug=False)

    global builder
    builder = Builder(build_queue, PRELOAD)
    builder.start()

    http_server = HTTPServer(application)
    http_server.listen(PORT)

    signal.signal(signal.SIGTERM, sig_handler)
    signal.signal(signal.SIGINT, sig_handler)

    print("Binder API server running on port {}".format(PORT))
    IOLoop.current().set_blocking_log_threshold(3)
    IOLoop.current().start()


if __name__ == "__main__":
    main()

