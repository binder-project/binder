import shutil
import os
import re

from settings import MainSettings
from binder.log import *

def namespace_params(ns, params):
    ns_params = {}
    for p in params:
        ns_params[ns + '.' + p] = params[p]
    return ns_params

def make_patterns(params):
    return [(re.compile("{{" + k + "}}"), '{0}'.format(params[k])) for k in params]

def fill_template_string(template, params):
    res = make_patterns(params)
    replaced = template
    for pattern, new in res:
        replaced = pattern.sub(new, replaced)
    return replaced

def fill_template(template_path, params):
    try:
        res = make_patterns(params)
        with open(template_path, 'r+') as template:
            raw = template.read()
        with open(template_path, 'w') as template:
            replaced = raw
            for pattern, new in res:
                replaced = pattern.sub(new, replaced)
            template.write(replaced)
    except (IOError, TypeError) as e:
        error_log("fill_template", "Could not fill template {0}: {1}".format(template_path, e))

def make_dir(path, clean=False):
    if os.path.isdir(path):
        if clean:
            shutil.rmtree(path)
            os.mkdir(path)
    else:
        os.mkdir(path)

def get_binder_home():
    import binder
    return "/".join(binder.__file__.split("/")[:-1])

def get_env_string():
    env = [
        "BINDER_HOME={}".format(MainSettings.ROOT),
        "KUBERNETES_PROVIDER={}".format(os.environ["KUBERNETES_PROVIDER"]),
        "PYTHONPATH=$PYTHONPATH:{}".format(get_binder_home())
    ]
    return " ".join(env)
