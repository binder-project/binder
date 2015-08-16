import tornado.ioloop
import tornado.web

from binder.service import Service
from binder.app import App

app = Flask(__name__)
pool = Pool(10)
queue = Queue()

@app.route("/apps/<organization>/<repo>", methods=["GET", "POST"])
def github_handler(organization, repo):
    if request.method == "POST":
        json = request.get_json()
        json["name"] = organization + "-" + repo
        json["repo"] = "https://github.com/{0}/{1}".format(organization, repo)
    elif request.method == "GET":
        pass

@app.route("/apps/<app_id>", methods=["GET", "POST"])
def other_source_handler(app_id):
    if request.method == "POST":
        pass
    elif request.method == "GET":
        pass

@app.route("/services", methods=["GET"])
def services():
    services = Service.get_service()
    return jsonify(map(lambda service: service.full_name, services))

@app.route("/apps", methods=["GET"])
def apps():
    services = Service.get_service()
    return jsonify(map(lambda service: service.full_name, services))

application = tornado.web.Application([ 
    (r"/
])
