import json

from multiprocessing import Process

import zmq
from zmq.eventloop.ioloop import IOLoop
from mdp import MDPWorker

from binder.settings import BinderDSettings

class BinderDModule(Process):

    TAG = "binderd"

    class Worker(MDPWorker):
        
        def __init__(self, module, context, url, tag):
            super(BinderDModule.Worker, self).__init__(context, url, tag)
            self.module = module

        def _process_return(self, msg):
            return bytes(json.dumps(msg))

        def on_request(self, msg):
            """
            MDPWorker interface
            """
            msg = json.loads(str(msg[0]))
            if not 'type' in msg:
                self.reply(self._process_return(self.module._error_msg("no type tag")))
            elif 'type' == 'stop':
                self.module._handle_stop()
                self.module.stop()
                rsp = self.module._success_msg("stopped module {}".format(self.module.TAG))
                self.reply(self._process_return(rsp))
            else:
                rsp = self.module._handle_message(msg)
                self.reply(self._process_return(rsp))

    def __init__(self):
        super(BinderDModule, self).__init__()
        self.name = self.__class__.__name__
        self.daemon = True
        self._stopped = False

    def _connect(self):
        context = zmq.Context()
        url = "{0}:{1}".format(BinderDSettings.BROKER_HOST, BinderDSettings.BROKER_PORT)
        worker = BinderDModule.Worker(self, context, url, bytes(self.TAG))
        IOLoop.instance().start()
        worker.shutdown()

    def _error_msg(self, error):
        return {"type": "error", "msg": error}

    def _success_msg(self, msg):
        return {"type": "success", "msg": msg}

    def _initialize(self):
        """
        Abstract method
        """
        pass

    def _handle_message(self, msg):
        """
        Abstract method
        """
        return self._success_msg("default response")

    def _handle_stop(self):
        """
        Abstract method
        """
        return self._success_msg("default response")

    def _get_message(self):
        pass

    def run(self):
        self._initialize()
        self._connect()
