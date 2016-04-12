from threading import Thread
import sys
import os
import Queue

from multiprocess import pool, Process
import multiprocessing

from binder.app import App
from binder.utils import make_dir

NUM_WORKERS = 5
GET_TIMEOUT = 2
LOG_DIR = "/home/andrew/logs/binder"

# Copied+pasted from http://stackoverflow.com/questions/6974695/python-process-pool-non-daemonic
# TODO use message queuing system instead of 2 process pools
class NoDaemonProcess(Process):
    # make 'daemon' attribute always return False
    def _get_daemon(self):
        return False
    def _set_daemon(self, value):
        pass
    daemon = property(_get_daemon, _set_daemon)

class NoDaemonPool(pool.Pool):
    Process = NoDaemonProcess

def build_app(spec, log_dir, preload=False):
    name = spec["name"]
    app = App.get_app(name)
    if app and app.build_state == App.BuildState.BUILDING:
        print("App {} already building. Wait for build to complete before resubmitting.".format(name))
        return
    new_app = App.create(spec)
    try:
        new_app.build(preload=preload)
    except Exception as e:
        # the "catch-all" clause
        print("Could not build app {}: {}".format(new_app.name, e))
        App.index.update_build_state(App.BuildState.FAILED)

class Builder(Thread):

    def __init__(self, queue, preload):
        super(Builder, self).__init__()
        self._build_queue = queue

        self._pool = NoDaemonPool(processes=NUM_WORKERS) 
        multiprocessing.freeze_support()

        self._stopped = False
        self._preload = preload

        make_dir(LOG_DIR)

    def stop(self):
        self._stopped = True
        self._pool.terminate()

    def _build(self, spec):
        try:
            pool = self._pool
            pool.apply_async(build_app, (spec, LOG_DIR, self._preload))
        except Exception as e:
            print("Exception in _build: {}".format(e))

    def run(self):
        while not self._stopped:
            try:
                next_job = self._build_queue.get(timeout=GET_TIMEOUT)
                print("Got job: {}".format(next_job))
                self._build(next_job)
            except Queue.Empty:
                pass

