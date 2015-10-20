
# Lists the available binderd modules and the type of client socket necessary to communicate with them

import zmq

modules = { 
    'log_reader': ("binder.binderd.log_reader", "LogReader"), 
    'log_writer': ("binder.binderd.log_writer", "LogWriter"),
    'kube_proxy': ("binder.binderd.kube_proxy", "KubeProxy")
}

