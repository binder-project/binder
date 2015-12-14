import logging
import sys
import types
import os
import sys
import json
import Queue
import re

from logging import Handler, FileHandler, StreamHandler, Formatter, Filter
from threading import Thread

import zmq 

from binder.app import App
from binder.settings import LogSettings
from binder.utils import make_dir
from binder.binderd.module import BinderDModule


class LogWriter(BinderDModule):

    TAG = "log_writer"

    ROOT_FORMAT = "%(asctime)s %(levelname)s: - %(message)s"
    BINDER_FORMAT = "%(asctime)s %(levelname)s: - %(tag)s: %(message)s"

    COLOR_RE = re.compile(r'\[\d+m')

    class PublisherThread(Thread):

        _singleton = None

        @staticmethod
        def get_instance():
            singleton = LogWriter.PublisherThread._singleton
            if not singleton or not singleton.is_alive(): 
                LogWriter.PublisherThread._singleton = LogWriter.PublisherThread()
                LogWriter.PublisherThread._singleton.start()
            return LogWriter.PublisherThread._singleton 

        def __init__(self):
            super(LogWriter.PublisherThread, self).__init__()
            self.daemon = True
            self._stopped = False
            self._queue = Queue.Queue()

            # start the publisher socket
            context = zmq.Context()
            self._pub_sock = context.socket(zmq.PUB)
            self._pub_sock.bind("{}:{}".format(LogSettings.PUBSUB_HOST, LogSettings.PUBSUB_PORT))

        def publish(self, topic, msg):
            self._queue.put((topic, msg))

        def stop(self): 
            self._stopped = True
            self._pub_sock.close()
    
        def run(self):
            while not self._stopped:
                try:
                    topic, msg = self._queue.get_nowait()
                    self._pub_sock.send_multipart([bytes(topic), bytes(msg)], flags=zmq.NOBLOCK) 
                except Queue.Empty:
                    continue
                except zmq.ZmqError:
                    continue


    class PublisherFilter(Filter):

        def filter(self, record):
            pass
                
    class PublisherHandler(Handler):

        def __init__(self):
            super(LogWriter.PublisherHandler, self).__init__()

        def emit(self, record):
            topic = record.app
            if topic:
                publisher = LogWriter.PublisherThread.get_instance()
                msg = self.format(record)
                publisher.publish(topic, msg)

    
    def __init__(self):
        super(LogWriter, self).__init__()
        self._stopped = None

        # set once the process has started
        self._app_loggers = None
        self._root_logger = None

    def stop(self):
        LogWriter.PublisherThread.get_instance().stop()
        self._stopped = True

    def _configure_root_loggers(self):
        make_dir(LogSettings.ROOT_DIRECTORY)
        log_dir = os.path.join(LogSettings.ROOT_DIRECTORY, "root")
        make_dir(log_dir)

        logging.basicConfig(format=LogWriter.ROOT_FORMAT)

        # zeromq publishing logger configuration
        self._stream_logger = logging.getLogger(__name__ + '-stream')
        self._stream_logger.setLevel(LogSettings.LEVEL)
        ph = LogWriter.PublisherHandler()
        ph.setFormatter(Formatter(LogWriter.BINDER_FORMAT))
        self._stream_logger.addHandler(ph)

        # root logger configuration
        self._root_logger = logging.getLogger(__name__) 
        self._root_logger.propagate = False
        self._set_logging_config(log_dir, LogSettings.ROOT_FILE, self._root_logger)

    def _set_logging_config(self, log_dir, name, logger):
        logger.setLevel(LogSettings.LEVEL)
        file_name = name + ".log"
        level = LogSettings.LEVEL
        formatter = Formatter(LogWriter.BINDER_FORMAT)

        # full output file config
        full_fh = FileHandler(os.path.join(log_dir, file_name))
        full_fh.setLevel(level)
        full_fh.setFormatter(formatter)

        # stdout output config
        sh = StreamHandler(sys.stdout)
        sh.setLevel(level)
        sh.setFormatter(formatter)

        logger.addHandler(full_fh)
        logger.addHandler(sh)
    
    def _make_app_loggers(self, name):
        raw = logging.getLogger(name)
        filtered = logging.getLogger(name + '-filtered')
        self._set_logging_config(LogSettings.APPS_DIRECTORY, name + '-filtered', filtered)
        self._set_logging_config(LogSettings.APPS_DIRECTORY, name, raw)
        loggers = (raw, filtered)
        self._app_loggers[name] = loggers
        return loggers

    def _configure_app_loggers(self):
        make_dir(LogSettings.APPS_DIRECTORY)
        apps = App.get_app()
        for app in apps:
            if not app.name in self._app_loggers:
                self._make_app_loggers(app.name)

    def _get_loggers(self, name):
        return self._app_loggers.get(name)

    def _initialize(self):
        super(LogWriter, self)._initialize()
        # set up the loggers
        self._app_loggers = {}
        self._root_logger = None

        self._configure_root_loggers()
        self._configure_app_loggers()

    def _handle_log(self, msg):
        level = msg.get("level")
        string = msg.get("msg")
        tag = msg.get("tag")
        app = msg.get("app")
        if not tag or not level or not string:
            return self._error_msg("malformed log message")
        try:
            result_msg = "message not logged"
            level = int(level)
            if app: 
                loggers = self._get_loggers(app)
                if not loggers: 
                    raw_logger, filtered_logger = self._make_app_loggers(app)
                else:
                    raw_logger, filtered_logger = loggers
            else:
                filtered_logger = None
                raw_logger = self._root_logger
            if level and string:
                m = LogWriter.COLOR_RE.search(string)
                if m:
                    start, stop = m.span()
                    string = string[:start] + string[stop:]
                result_msg = "message logged as {0}".format(level)
                del msg['msg']
                raw_logger.log(level, string, extra=msg)
                if not msg.get('no_publish'):
                    filtered_logger.log(level, string, extra=msg)
                    self._stream_logger.log(level, string, extra=msg)
        except Exception as e:
            return self._error_msg("logging error: {}".format(e))
        return self._success_msg(result_msg)

    def _handle_message(self, msg):
        """
        BinderDModule interface
        """
        msg_type = msg.get("type") 
        if msg_type == 'log': 
            return self._handle_log(msg)

