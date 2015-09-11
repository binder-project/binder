import json

import zmq
from zmq.eventloop.ioloop import IOLoop

from mdp import MDPWorker

from binder.settings import BinderDSettings

class BinderDModule(Process):

    TAG = "binderd"

    class Worker(MDPWorker):
        
        def __init__(self, module, context, url, tag):
            super(MDPWorker, self).__init__(context, url, tag)
            self.module = module

        def on_request(self, msg):
            """
            MDPWorker interface
            """
            msg = json.loads(msg)
            if not 'type' in msg:
                continue
            elif 'type' == 'stop':
                self.module._handle_stop()
                self.module.stop()
            else:
                self.module._handle_message(msg)

    def __init__(self):
        self.daemon = True
        self._stopped = False

    def _connect(self):
        context = zmq.Context()
        url = "{0}:{1}".format(BinderDSettings.BROKER_HOST, BinderDSettings.BROKER_PORT)
        worker = BinderDModule.Worker(context, url, bytes(self.TAG))
        IOLoop.instance().start()
        worker.shutdown()

    def _initialize(self):
        """
        Abstract method
        """
        pass

    def _handle_message(self, msg):
        """
        Abstract method
        """
        pass

    def _handle_stop(self):
        """
        Abstract method
        """
        pass

    def _get_message(self):
        pass

    def run(self):
        self._initialize()
        self._connect()
