import logging
from Queue import Queue
from threading import Thread

from binder.binderd.client import BinderClient

class LoggerClient(Thread):

    _singleton = None

    @staticmethod
    def getInstance():
        if not LoggerClient._singleton:
            LoggerClient._singleton = LoggerClient()
        return LoggerClient._singleton

    def __init__(self):
        super(Thread, self).__init__()
        self._stopped = False

        self._queue = Queue()
        self._client = BinderClient("log_writer")

    def stop(self): 
        self._client.close()
        self._stopped= True

    def run(self):
        while not self._stopped:
            try:
                if not self._queue.empty():
                    msg = self._queue.get()
                    self._client.send(msg)
            except Queue.Empty:
                # if the queue is empty, continue to the next iteration
                pass

    def _send(self, msg):
        self._queue.put(msg)

    def debug(self, tag, msg, app=None):
        self._send({'type': 'log', 'level': logging.DEBUG, 'msg': msg, 'tag': tag, 'app': app})

    def info(self, tag, msg, app=None):
        self._send({'type': 'log', 'level': logging.INFO, 'msg': msg, 'tag': tag, 'app': app})

    def warn(self, tag, msg, app=None):
        self._send({'type': 'log', 'level': logging.WARNING, 'msg': msg, 'tag': tag, 'app': app})

    def error(self, tag, msg, app=None):
        self._send({'type': 'log', 'level': logging.ERROR, 'msg': msg, 'tag': tag, 'app': app})

def debug_log(tag, msg):
    log = LoggerClient.getInstance()
    log.debug(tag, msg)

def info_log(tag, msg):
    log = LoggerClient.getInstance()
    log.info(tag, msg)

def warning_log(tag, msg):
    log = LoggerClient.getInstance()
    log.warning(tag, msg)

def error_log(tag, msg):
    log = LoggerClient.getInstance()
    log.error(tag, msg)

