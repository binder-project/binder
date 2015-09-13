import logging
import Queue
import time

from threading import Thread

import zmq

from binder.binderd.client import BinderClient

class LoggerClient(Thread):

    _singleton = None

    @staticmethod
    def getInstance():
        if not LoggerClient._singleton:
            client = LoggerClient()
            client.start()
            LoggerClient._singleton = client
        return LoggerClient._singleton

    def __init__(self):
        super(LoggerClient, self).__init__()
        self.daemon = True
        self._stopped = False

        self._queue = Queue.Queue()
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


class SubStreamReader(Thread):

    def __init__(self, buf):
        super(StreamReader, self).__init__()
        self._stopped = False
        self._buf = buf

    def stop(self):
        self._stopped = True

    def run(self):
        context = zmq.Context()
        socket = context.socket(zmq.SUB)
        socket.setsockopt(zmq.SUBSCRIBE, bytes(app if app else "root"))
        socket.connect("{}:{}".format(LogSettings.PUBSUB_HOST, LogSettings.PUBSUB_PORT))
        while not self._stopped:
            msg = str(socket.recv())
            # buffer the message
            self._buf.put(msg)


def debug_log(tag, msg, app=None):
    log = LoggerClient.getInstance()
    log.debug(tag, msg, app)

def info_log(tag, msg, app=None):
    log = LoggerClient.getInstance()
    log.info(tag, msg, app)

def warning_log(tag, msg, app=None):
    log = LoggerClient.getInstance()
    log.warning(tag, msg, app)

def error_log(tag, msg, app=None):
    log = LoggerClient.getInstance()
    log.error(tag, msg, app)

def write_stream(tag, level_string, stream, app=None):
    def _process_stream(stream):
        log = LoggerClient.getInstance()
        if level_string not in LoggerClient.__dict__: 
            log.error("LoggerClient", "write_stream failing with unexpected level_string: {}".format(level_string))
            return
        method = log.__getattribute__(level_string)
        for line in iter(stream.readline, ''):
            method(tag, line, app=app)
    t = Thread(target=_process_stream, args=(stream,))
    t.start()
            
def read_stream(app=None, start_time=None, level=None):
    # 1) open a REQ socket (using the standard binderd protocol) and get all logs starting at start_time
    # 2) simultaneously, buffering the output from a log_reader subscriber socket (with app name as topic) and 
    #    read until closed
    # 3) write out all the logs from the RSP, recording the last timestamp of each 
    # 4) once RSP is exhausted, write out all subscriber messages after last RSP timestamp
    def _stream_generator():
        buf = Queue()
        sub_thread = SubStreamReader(buf)
        sub_thread.start()
        bc = BinderClient("log_reader")
        lines = bc.send({"type": "get", "app": app, "since": start_time}).get("msg")

        # exhaust all lines from the get request
        last_time = None
        for line in lines:
            last_time = LogSettings.EXTRACT_TIME(line)
            yield line
        last_time = time.strptime(last_time, LogSettings.TIME_FORMAT)
        
        # now start reading the subscriber output (starting strictly after last_time)
        for line in buf.get():
            line_time = LogSettings.EXTRACT_TIME(line)
            if line_time > last_time:
                yield line
           
