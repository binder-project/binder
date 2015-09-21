import Queue
import json
import signal
import time
import datetime
import threading

from tornado import gen
from tornado.ioloop import IOLoop
from tornado.web import Application, RequestHandler
from tornado.httpserver import HTTPServer
from tornado.websocket import WebSocketHandler

from binder.service import Service
from binder.app import App
from binder.cluster import ClusterManager
from binder.log import AppLogStreamer 
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

    def get(self):
        if ALLOW_ORIGIN:
            self.set_header('Access-Control-Allow-Origin', '*')

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

    def get(self, organization, repo):
        super(GithubStatusHandler, self).get()
        app_name = App.make_app_name(organization, repo)
        app = App.get_app(app_name)
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
        app = App.get_app(app_name)
        if app and app.build_state == App.BuildState.COMPLETED:
            redirect_url = app.deploy("single-node")
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

    def get(self):
        super(ServicesHandler, self).get()
        services = Service.get_service()
        self.write({"services": [service.full_name for service in services]})

class AppsHandler(BinderHandler):

    def get(self):
        super(AppsHandler, self).get()
        apps = App.get_app()
        self.write({"apps": [app.name for app in apps]})

class CapacityHandler(BinderHandler):

    POLL_PERIOD = 3600

    cached_capacity = None
    last_poll = None
    
    def get(self):
        super(CapacityHandler, self).get()
        cm = ClusterManager.get_instance()
        # don't count the default and kube-system namespaces
        running = len(cm.get_running_apps()) - 3
        if not self.last_poll or not self.cached_capacity or\
                time.time() - self.last_poll > CapacityHandler.POLL_PERIOD:
            capacity = cm.get_total_capacity()
            CapacityHandler.cached_capacity = capacity
            CapacityHandler.last_poll = time.time()
        self.write({"capacity": self.cached_capacity, "running": running})


class BuildLogsHandler(WebSocketHandler):

    def __init__(self, application, request, **kwargs):
        super(BuildLogsHandler, self).__init__(application, request, **kwargs)
        self._thread = None

    def stop(self):
        if self._thread:
            self._thread.stop()
            self._thread.join()
            ws_handlers.remove(self)

    def check_origin(self, origin):
        return True

    def open(self, organization, repo):
        super(BuildLogsHandler, self).open()
        print("Opening websocket for {}/{}".format(organization, repo))
        app_name = App.make_app_name(organization, repo)
        app = App.get_app(app_name)
        time_string = datetime.datetime.strftime(app.last_build_time, LogSettings.TIME_FORMAT)

        ws_handlers.append(self)

        self._thread = AppLogStreamer(app_name, time_string, self.write_message)
        self._thread.start()

    def on_message(self, message):
        pass

    def on_close(self):
        super(BuildLogsHandler, self).on_close()
        self.stop()


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
        (r"/apps/(?P<organization>.+)/(?P<repo>.+)/logs", BuildLogsHandler),
        (r"/apps/(?P<organization>.+)/(?P<repo>.+)", GithubBuildHandler),
        (r"/apps/(?P<app_id>.+)", OtherSourceHandler),
        (r"/services", ServicesHandler),
        (r"/apps", AppsHandler),
        (r"/capacity", CapacityHandler)
    ], debug=True)

    signal.signal(signal.SIGTERM, sig_handler)
    signal.signal(signal.SIGINT, sig_handler)

    global builder
    builder = Builder(build_queue, PRELOAD)
    builder.start()

    http_server = HTTPServer(application)
    http_server.listen(PORT)

    print("Binder API server running on port {}".format(PORT))
    IOLoop.current().start()


if __name__ == "__main__":
    main()

