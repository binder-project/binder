import logging
import sys
import types
import os
import sys
import json

from logging.handlers import FileHandler, StreamHandler
from Queue import Queue as ThreadQueue
from multiprocessing import Queue as ProcessQueue, Process
from threading import Lock

import zmq 

from binder.app import App
from binder.settings import LogSettings
from binder.utils import make_dir


class LogWriter(BinderDModule):

    TAG = "LogWriter"

    def start_module(self):
        self._logging_proc = LoggingProcess()
        self._logging_proc.start()
        return logging_proc


def LoggingProcess(Process):

    ROOT_FORMAT = "%(asctime)s - %(tag)s: %(message)s"
    APP_FORMAT = "%(asctime)s - %(app)s:%(tag)s: %(message)s"
    
    def __init__(self, proc_queue, app_name="system"):
        self._stopped = None

        self._app_formatter = logging.Formatter(LoggingProcess.APP_FORMAT)
        self._root_formatter = logging.Formatter(LoggingProcess.ROOT_FORMAT)

        self._app_loggers = {}
        self._root_logger = None

        self._configure_root_logger()
        self._configure_app_loggers()

    def stop(self):
        self._stopped = True

    def _configure_root_logger(self):
        make_dir(LogSettings.ROOT_DIRECTORY)
        log_dir = os.path.join(LogSettings.ROOT_DIRECTORY, "root")
        make_dir(log_dir)

        logging.basicConfig(format=LoggingProcess.ROOT_FORMAT)
        self._root_logger = logging.getLogger(__name__) 

        self._set_logging_config(log_dir, LogSettings.ROOT_FILE, self._root_formatter, self._root_logger)

    def _set_logging_config(self, log_dir, name, formatter, logger)

        # full output file config
        full_fh = FileHandler(os.path.join(log_dir, name))
        full_fh.setLevel(LogSettings.LEVEL)
        full_fh.setFormatter(formatter)

        # stream output config
        sh = StreamHandler(sys.stdout)
        sh.setLevel(LogSettings.LEVEL)
        sh.setFormatter(formatter)

        logger.addHandler(full_fh)
        logger.addHandler(sh)
    
    def _make_app_logger(self, app):
        logger = logging.getLogger(app)
        self._set_logging_config(LogSettings.APPS_DIRECTORY, app + ".log", self._app_formatter, logger)
        logger.
        return logger

    def _configure_app_loggers(self):
        make_dir(LogSettings.APPS_DIRECTORY)
        apps = App.get_app()
        for app in apps:
            if not app in self._app_loggers:
                logger = self._make_app_logger(app.name)
                self._app_loggers[app.name] = logger 

    def _get_logger(app):
        return self._app_loggers.get(app)

    def _handle_stop(self, msg):
        self.stop()

    def _handle_log(self, msg):
        level = msg.get("level")
        string = msg.get("msg")
        tag = msg.get("tag")
        app = msg.get("app")
        extra = {'tag': tag}
        if app: 
            logger = self._get_logger(app)
            if not logger:
                logger = self._make_app_logger(app)
            extra['app'] = app
        else:
            logger = self._root_logger
        if level and msg:
            if level == logging.DEBUG:
                logger.debug(msg, extra=extra)  
            elif level == logging.INFO:
                logger.info(msg, extra=extra)  
            elif level == logging.WARNING:
                logger.warning(msg, extra=extra)  
            elif level == logging.ERROR:
                logger.error(msg, extra=extra)  

    def run(self):
        # configure control socket
        # TODO: as of now, the pub/sub socket is also the control socket (for stop messages)

        # configure subscriber socket
        ctx = zmq.Context()
        sub = ctx.socket(zmq.SUB)
        sub.bind('%s:%i' % (LogSettings.HOST, LogSettings.PORT))
        sub.setsockopt(zmq.SUBSCRIBE, LogWriter.TAG)

        while not self._stopped:
            try: 
                topic, msg_string = sub.recv_multipart(flags=zmq.NOBLOCK)
                msg = json.loads(msg_string) 
                msg_type = msg.get("type") 
                if not msg_type:
                    continue
                if msg_type == 'stop': 
                    self._handle_stop(msg)
                elif msg_type == 'log': 
                    self._handle_log(msg)
            except zmq.ZMQError:
                # if the queue is empty, continue to the next iteration
                pass

