from multiprocessing import Pool
import Queue
import json

import tornado.ioloop
from tornado import gen
from tornado.web import Application, RequestHandler
from tornado.httpserver import HTTPServer

from binder.service import Service
from binder.app import App

from .builder import Builder

PORT = 8080
NUM_WORKERS = 10
QUEUE_SIZE = 50

build_queue = Queue.Queue(QUEUE_SIZE)
builder = Builder()

class BuildHandler(RequestHandler):

    def _is_malformed(self, spec):
        # by default, there aren't any required fields in an app specification
        pass


class GithubHandler(BuildHandler):

    def _is_malformed(self, spec):
        # in the GithubHandler, the repo field is inferred from organization/repo
        return "repo" in spec

    def _make_app_name(self, organization, repo):
        return organization + "-" + repo

    @gen.coroutine
    def get(self, organization, repo):
        # if the app is still building, return an error. If the app is built, deploy it and return
        # the redirect url
        app_name = self._make_app_name(organization, repo)
        app = App.get_app(app_name)
        if not app:
            self.set_status(404)
            self.write({"error": "app does not exist"})
        else:
            if app.build_state == App.BuildState.BUILDING:
                self.write({"build_status": "building"})
            elif app.build_state == App.BuildState.FAILED:
                self.write({"build_status": "failed"})
            elif app.build_state == App.BuildState.COMPLETED:
                redirect_url = app.deploy()
                self.write({"redirect_url": redirect_url})

    def post(self, organization, repo):
        # if the spec is properly formed, create/build the app
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

class ServicesHandler(RequestHandler):
    def get():
        pass

class AppsHandler(RequestHandler):
    def get():
        pass

def github_handler(organization, repo):
    if request.method == "POST":
        json = request.get_json()
        json["name"] = organization + "-" + repo
        json["repo"] = "https://github.com/{0}/{1}".format(organization, repo)
    elif request.method == "GET":
        pass

def other_source_handler(app_id):
    if request.method == "POST":
        pass
    elif request.method == "GET":
        pass

def services():
    services = Service.get_service()
    return jsonify(map(lambda service: service.full_name, services))

def apps():
    services = Service.get_service()
    return jsonify(map(lambda service: service.full_name, services))

def main():
    application = Application([
        (r"/apps/(?P<organization>\w+)/(?P<repo>\w+)", GithubHandler),
        (r"/apps/(?P<app_id>\w+)", OtherSourceHandler),
        (r"/services", ServicesHandler),
        (r"/apps", AppsHandler)
    ])
    builder.start()
    http_server = HTTPServer(application)
    http_server.listen(PORT)

if __name__ == "__main__":
    main()

