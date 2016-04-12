import json

import zmq 
from mdp.client import MDPClient, mdp_request

from binder.settings import LogSettings, BinderDSettings
from binder.binderd import modules

class BinderClient(object):

    def __init__(self, name="binderd"):
        if name not in modules and name != "binderd":
            raise Exception("Cannot connect to a nonexistent module")

        self.name = name
        self.module = modules.get(self.name)
        self._sock = None
        self._connect()
    
    def _connect(self):
        if self.name == "binderd":
            # connect to the binderd control socket
            pass
        else:
            # connect to the module through the binderd broker
            context = zmq.Context()
            socket = context.socket(zmq.REQ)
            socket.setsockopt(zmq.LINGER, 0)
            url = "{0}:{1}".format(BinderDSettings.BROKER_HOST, BinderDSettings.BROKER_PORT)
            socket.connect(url)
            self._sock = socket

    def send(self, msg):
        if not self._sock:
            raise Exception("BinderClient not connected. Cannot send")

        if not isinstance(msg, str):
            if isinstance(msg, dict):
                msg = json.dumps(msg)
            else:
                raise ValueError("cannot send message of type: {}".format(type(msg)))

        if self.name == "binderd":
            # sending msg to a standard RES socket
            pass
        else:
            # using MDP module to send to service
            res = mdp_request(self._sock, bytes(self.name), [bytes(msg),], 10)
            # the first element in the list is the service name
            return json.loads(res[1]) if res else None

    def __enter__(self):
        return self

    def __exit__(self):
        self.close()

    def close(self):
        self._sock.close()
        
    def stop_daemon(self):
        if self.name != "binderd":
            raise Exception("Cannot stop binderd using a module-specific client")
        self.send({"type": "stop"})

    def start_module(self, name):
        if self.name != "binderd":
            raise Exception("Cannot start module using a module-specific client")
        self.send({"type": "start", "name": name})

    def stop_module(self, name):
        if self.name != "binderd":
            raise Exception("Cannot stop module using a module-specific client")
        self.send({"type": "stop", "name": name})
