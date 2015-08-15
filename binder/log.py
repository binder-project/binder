import logging
import sys
from threading import Lock

from binder.settings import LOG_FILE, LOG_LEVEL

class Logger(object):

    _singleton = None
    log_lock = Lock()

    @staticmethod
    def getInstance():
        if not Logger._singleton:
            logging.basicConfig(filename=LOG_FILE, level=LOG_LEVEL)
            Logger._singleton = logging.getLogger(__name__)
            Logger.configure(Logger._singleton)
        return Logger._singleton

    @staticmethod
    def configure(logger):
        """
        Set the log message format, threshold, etc here...
        """
        pass

def lock_method(log_func):
    def log(msg):
        Logger.log_lock.acquire()
        try:
            log_func(msg)
        except Exception:
            pass
        Logger.log_lock.release()
    return log

@lock_method
def debugLog(msg):
    log = Logger.getInstance()
    log.debug(msg)

@lock_method
def infoLog(msg):
    log = Logger.getInstance()
    log.info(msg)

@lock_method
def warningLog(msg):
    log = Logger.getInstance()
    log.warning(msg)

@lock_method
def errorLog(msg):
    log = Logger.getInstance()
    log.error(msg)
