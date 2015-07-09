#!/usr/bin/python
import argparse
import os
import json

"""
Indices
"""

class AppIndex(object):
    """
    Responsible for finding and managing metadata about apps.
    """
    def find_apps(self):
        pass


class ModuleIndex(object):
    """
    Responsible for finding and managing metadata about modules
    """
    def find_modules(self):
        pass


class FileModuleIndex(ModuleIndex):
    """
    Finds/manages modules by searching for a certain directory structure in a directory hierarchy
    """
    def __init__(self, root):
        pass


class FileAppIndex(AppIndex):
    """
    Finds/manages apps by searching for a certain directory structure in a directory hierarchy
    """
    def __init__(self, root):
        pass


class IndexFactory(object):

    @staticmethod
    def get_indices(*args):
        return FileAppIndex(*args), FileModuleIndex(*args)

"""
Build section
"""

ROOT = os.environ["POD_SERVER_HOME"]

def handle_build(args):
    print("In handle_build, args: {0}".format(str(args)))

    app_index, module_index = IndexFactory.get_indices(ROOT)

    if args.subcmd == "module":
        build_module(module)
    elif args.subcmd == "app":
        build_app(app)

def build_module(module):
    pass

def build_app(app):
    pass

def _build_subparser(parser):
    p = parser.add_parser("build", description="Build modules or applications")
    s = p.add_subparsers(dest="subcmd")

    module = s.add_parser("module")
    module.add_argument("name", help="Name of module to build", nargs="*")
    module.add_argument("--upload", required=False, help="Upload module after building")
    module.add_argument("--all", required=False, help="Build all modules")

    app = s.add_parser("app")
    app.add_argument("name", help="Name of app to build", nargs="*")

"""
List section
"""

def handle_list(args):
    print("In handle_list, args: {0}".format(str(args)))

    app_index, module_index = IndexFactory.get_indices(ROOT)

    if args.subcmd == "modules":
        list_modules(module_index)
    elif args.subcmd == "apps":
        list_apps(app_index)

def list_modules(module_index):
    modules = module_index.get_modules()
    print "Available modules:"
    for module in modules:
        print(" {0}".format(module['name']))
        for version in module['versions']:
            print("  {0} - last built: {1}".format(version['name'], version['build_time']))

def list_apps(app_index):
    apps = app_index.get_apps()
    print "Available apps:"
    for app in apps:
        print(" {0} - last built: {1}`".format(app['name'], app['build_time']))

def _list_subparser(parser):
    p = parser.add_parser("list", description="List modules or applications")
    s = p.add_subparsers(dest="subcmd")

    mod_parser = s.add_parser("modules")
    app_parser = s.add_parser("apps")

"""
Deploy section
"""

def handle_deploy(args):
    print("In handle_deploy, args: {0}".format(str(args)))

    if args.subcmd == "module":
        list_modules()
    elif args.subcmd == "app":
        list_apps()

def deploy_app(app):
    pass

def _deploy_subparser(parser):
    p = parser.add_parser("deploy", description="Deploy applications")
    s = p.add_subparsers(dest="subcmd")

    s.add_parser("module")
    s.add_parser("app")

"""
Upload section
"""

def handle_upload(args):
    print("In handle_upload, args: {0}".format(str(args)))

def _upload_subparser(parser):
    p = parser.add_parser("upload", description="Upload modules or applications")
    s = p.add_subparsers(dest="subcmd")

    s.add_parser("module")
    s.add_parser("app")

"""
Main section
"""

if __name__ == "__main__":

    if not ROOT:
        raise Exception("POD_SERVER_HOME environment variable needs to be set")

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

