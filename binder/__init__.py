import signal
from binder.log import LoggerClient

def sig_handler(sig, frame):
    LoggerClient.getInstance().stop()

signal.signal(signal.SIGTERM, sig_handler)
signal.signal(signal.SIGINT, sig_handler)
