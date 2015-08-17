from threading import Thread
from pathos.multiprocessing import Pool
import sys
import os

from binder.app import App

def build_app(spec):
    new_app = App.create(spec)
    if new_app:
        new_app.build()

class Builder(Thread):

    NUM_WORKERS = 10

    def __init__(self, queue):
        super(Builder, self).__init__()
        self._build_queue = queue
        self._pool = Pool(processes=Builder.NUM_WORKERS)
        self._stopped = False

    def stop(self):
        self._stopped = True

    def _build(self, spec):
        pool = self._pool
        pool.apply_async(build_app, (spec,))

    def run(self):
        while not self._stopped:
            next_job = self._build_queue.get()
            print("Got job: {}".format(next_job))
            self._build(next_job)

