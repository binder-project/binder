import Queue
import json
import signal

from tornado import gen
from tornado.ioloop import IOLoop
from tornado.web import Application, RequestHandler
from tornado.httpserver import HTTPServer

from binder.service import Service
from binder.app import App

from .builder import Builder

# TODO move settings into a config file
PORT = 8080
NUM_WORKERS = 10
PRELOAD = True
QUEUE_SIZE = 50
ALLOW_ORIGIN = True

build_queue = Queue.Queue(QUEUE_SIZE)

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

    def _make_app_name(self, organization, repo):
        return organization + "-" + repo


class GithubStatusHandler(GithubHandler):

    def get(self, organization, repo):
        super(GithubStatusHandler, self).get()
        app_name = self._make_app_name(organization, repo)
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
        app_name = self._make_app_name(organization, repo)
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
                spec["name"] = self._make_app_name(organization, repo)
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

def sig_handler(sig, frame):
    IOLoop.instance().add_callback(shutdown)

def shutdown():
    print("Shutting down...")
    IOLoop.instance().stop()
    builder.stop()

def main():

    application = Application([
        (r"/apps/(?P<organization>.+)/(?P<repo>.+)/status", GithubStatusHandler),
        (r"/apps/(?P<organization>.+)/(?P<repo>.+)", GithubBuildHandler),
        (r"/apps/(?P<app_id>.+)", OtherSourceHandler),
        (r"/services", ServicesHandler),
        (r"/apps", AppsHandler)
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

