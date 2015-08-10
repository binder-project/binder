#!/usr/bin/python

import argparse

from binder.cluster import ClusterManager
from binder.service import Service
from binder.app import App

"""
Build section
"""

def handle_build(args):
    print("In handle_build, args: {0}".format(str(args)))
    if args.subcmd == "service":
        build_service(args)
    elif args.subcmd == "app":
        build_app(args)

def build_service(args):
    service = Service.get_service(name=args.name)
    if isinstance(service, list):
        for s in service:
            s.build()
    elif service:
        service.build()
    else:
        print("Service {0} not found".format(service))

def build_app(args):
    apps = App.get_app(name=args.name)
    if isinstance(apps, list):
        for app in apps:
            app.build()
    elif isinstance(apps, App):
        apps.build()
    else:
        print("App {0} not found".format(apps))

def _build_subparser(parser):
    p = parser.add_parser("build", description="Build services or applications")
    s = p.add_subparsers(dest="subcmd")

    service = s.add_parser("service")
    service.add_argument("name", help="Name of service to build", nargs="?")
    service.add_argument("--upload", required=False, help="Upload service after building")
    service.add_argument("--all", required=False, help="Build all services")

    app = s.add_parser("app")
    app.add_argument("name", help="Name of app to build", type=str)


"""
List section
"""

def handle_list(args):
    if args.subcmd == "services":
        list_services()
    elif args.subcmd == "apps":
        list_apps()

def list_services():
    services = Service.get_service()
    print "Available services:"
    for service in services:
        print(" {0}".format(service.full_name))

def list_apps():
    apps = App.get_app()
    print "Available apps:"
    for app in apps:
        print(" {0} - last built: {1}".format(app.name, app.build_time))

def _list_subparser(parser):
    p = parser.add_parser("list", description="List services or applications")
    s = p.add_subparsers(dest="subcmd")

    service_parser = s.add_parser("services")
    app_parser = s.add_parser("apps")

"""
Deploy section
"""

def handle_deploy(args):
    print("In handle_deploy, args: {0}".format(str(args)))

    if args.subcmd == "service":
        raise NotImplementedError
    elif args.subcmd == "app":
        deploy_app(args)

def deploy_app(args):
    app = App.get_app(name=args.name)
    if app:
        app.deploy(mode=args.mode)
    else:
        print("App {0} not found".format(app))

def _deploy_subparser(parser):
    p = parser.add_parser("deploy", description="Deploy applications")
    s = p.add_subparsers(dest="subcmd")

    app = s.add_parser("app")
    app.add_argument("name", help="Name of app to deply", type=str)
    app.add_argument("mode", help="Deployment mode (i.e. 'single-mode', 'multi-node',...)" , type=str)

"""
Upload section
"""

def handle_upload(args):
    print("In handle_upload, args: {0}".format(str(args)))

def _upload_subparser(parser):
    p = parser.add_parser("upload", description="Upload services or applications")
    s = p.add_subparsers(dest="subcmd")

    s.add_parser("service")
    s.add_parser("app")

"""
Cluster section
"""

def _cluster_subparser(parser):
    p = parser.add_parser("cluster", description="Manage the cluster")
    s = p.add_subparsers(dest="subcmd")

    s.add_parser("start")
    s.add_parser("stop")

def handle_cluster(args):
    if args.subcmd  == "start":
        ClusterManager.get_instance().start()
    elif args.subcmd == "stop":
        ClusterManager.get_instance().stop()

choices = {
    "list": {
        "parser": _list_subparser,
        "handler": handle_list
    },
    "deploy": {
        "parser": _deploy_subparser,
        "handler": handle_deploy
    },
    "upload": {
        "parser": _upload_subparser,
        "handler": handle_upload
    },
    "build": {
        "parser": _build_subparser,
        "handler": handle_build
    },
    "cluster": {
        "parser": _cluster_subparser,
        "handler": handle_cluster
    }
}

parser = argparse.ArgumentParser(description="Launch generic Python applications on a Kubernetes cluster")
subparsers = parser.add_subparsers(dest="cmd")
for c in choices:
    choices[c]["parser"](subparsers)

args = parser.parse_args()

for c in choices:
    if args.cmd == c:
        choices[c]["handler"](args)
        break
