import logging
import sys
import types
import os
import sys
import json

from logging import FileHandler, StreamHandler

import zmq 

from binder.app import App
from binder.settings import LogSettings
from binder.utils import make_dir
from binder.binderd.module import BinderDModule


class LogWriter(BinderDModule):

    TAG = "log_writer"

    ROOT_FORMAT = "%(asctime)s - %(tag)s: %(message)s"
    
    def __init__(self):
        super(LogWriter, self).__init__()
        self._stopped = None

        # set once the process has started
        self._app_loggers = None
        self._root_logger = None

    def stop(self):
        self._stopped = True

    def _configure_root_logger(self):
        make_dir(LogSettings.ROOT_DIRECTORY)
        log_dir = os.path.join(LogSettings.ROOT_DIRECTORY, "root")
        make_dir(log_dir)

        logging.basicConfig(format=LogWriter.ROOT_FORMAT)
        self._root_logger = logging.getLogger(__name__) 

        self._set_logging_config(log_dir, LogSettings.ROOT_FILE, self._root_logger)

    def _set_logging_config(self, log_dir, name, logger):

        # full output file config
        full_fh = FileHandler(os.path.join(log_dir, name))
        full_fh.setLevel(LogSettings.LEVEL)

        # stream output config
        sh = StreamHandler(sys.stdout)
        sh.setLevel(LogSettings.LEVEL)

        logger.addHandler(full_fh)
        logger.addHandler(sh)
    
    def _make_app_logger(self, app):
        logger = logging.getLogger(app)
        self._set_logging_config(LogSettings.APPS_DIRECTORY, app + ".log", logger)
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

    def _initialize(self):
        super(LogWriter, self)._initialize()
        # set up the loggers
        self._app_loggers = {}
        self._root_logger = None

        self._configure_root_logger()
        self._configure_app_loggers()

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

    def _handle_message(self, msg):
        """
        BinderDModule interface
        """
        msg_type = msg.get("type") 
        if msg_type == 'log': 
            self._handle_log(msg)

