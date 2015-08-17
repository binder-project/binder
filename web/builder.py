from threading import Thread
from pathos.multiprocessing import Pool
import sys
import os

from binder.app import App

def build_app(spec, preload=False):
    new_app = App.create(spec)
    if new_app and new_app.build_state != App.BuildState.BUILDING:
        new_app.build(preload=preload)

class Builder(Thread):

    NUM_WORKERS = 10

    def __init__(self, queue, preload):
        super(Builder, self).__init__()
        self._build_queue = queue
        self._pool = Pool(processes=Builder.NUM_WORKERS)
        self._stopped = False
        self._preload = preload

    def stop(self):
        self._stopped = True

    def _build(self, spec):
        pool = self._pool
        pool.apply_async(build_app, (spec, self._preload))

    def run(self):
        while not self._stopped:
            next_job = self._build_queue.get()
            print("Got job: {}".format(next_job))
            self._build(next_job)

