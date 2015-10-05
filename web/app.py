import Queue
import json
import signal
import time
import datetime
import threading
from threading import Thread

from tornado import gen
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

    def get(self):
        if ALLOW_ORIGIN:
            self.set_header('Access-Control-Allow-Origin', '*')

    def _get_app(self, app_name):
        return gen.maybe_future(App.get_app(app_name))

    def _get_services(self):
        return gen.maybe_future(Service.get_service())

    def _get_apps(self):
        return gen.maybe_future(App.get_app())

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
        self.write({"apps": [app.name for app in apps]})

class CapacityHandler(BinderHandler):

    POLL_PERIOD = 3600

    cached_capacity = None
    last_poll = None

    def _get_capacity(self, cm):
        return gen.maybe_future(cm.get_total_capacity())
    
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

    @gen.coroutine
    def get(self, organization, repo):
        super(StaticLogsHandler, self).get()
        app_name = App.make_app_name(organization, repo)
        app = yield self._get_app(app_name)
        time_string = datetime.datetime.strftime(app.last_build_time, LogSettings.TIME_FORMAT)
        self.write({"logs": get_app_logs(app_name, time_string)})
        

class LiveLogsHandler(WebSocketHandler):

    class LogsThread(Thread):
        
        def __init__(self, handler, stream):
            super(LiveLogsHandler.LogsThread, self).__init__()
            self._stream = stream
            self._handler = handler
            self._stopped = False

        def stop(self):
            self._stopped = True

        def run(self):
            while not self._stopped:
                try: 
                    msg = self._stream.next()
                    if msg:
                        self._handler.write_message(msg)
                except StopIteration:
                    self.stop()
                
    def __init__(self, application, request, **kwargs):
        super(LiveLogsHandler, self).__init__(application, request, **kwargs)
        self._stream = None
        self._streamer = None
        self._periodic_cb = None

    def stop(self):
        if self._thread:
            self._thread.stop()
            ws_handlers.remove(self)

    def check_origin(self, origin):
        return True

    def _write_stream(self):
        if self._stream:
            try: 
                msg = self._stream.next()
                if not msg:
                    return
                self.write_message(msg)
            except StopIteration:
                self.stop()

    def open(self, organization, repo):
        super(LiveLogsHandler, self).open()
        print("Opening websocket for {}/{}".format(organization, repo))
        app_name = App.make_app_name(organization, repo)
        app = App.get_app(app_name)
        time_string = datetime.datetime.strftime(app.last_build_time, LogSettings.TIME_FORMAT)

        ws_handlers.append(self)

        self._streamer = AppLogStreamer(app_name, time_string)
        self._stream = self._streamer.get_stream()
        self._thread = LiveLogsHandler.LogsThread(self, self._stream)
        self._thread.start()

    def on_message(self, message):
        pass

    def on_close(self):
        super(LiveLogsHandler, self).on_close()
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
        (r"/apps/(?P<organization>.+)/(?P<repo>.+)/logs/static", StaticLogsHandler),
        (r"/apps/(?P<organization>.+)/(?P<repo>.+)/logs/live", LiveLogsHandler),
        (r"/apps/(?P<organization>.+)/(?P<repo>.+)", GithubBuildHandler),
        (r"/apps/(?P<app_id>.+)", OtherSourceHandler),
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
    IOLoop.current().start()


if __name__ == "__main__":
    main()

