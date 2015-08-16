from threading import Thread
from multiprocessing import Pool

from binder.app import App

def build_app(spec):
    new_app = App.create(job)
    if new_app:
        new_app.build()

class Builder(Thread):

    NUM_WORKERS = 15

    def __init__(self):
        self._pool = Pool(Builder.NUM_WORKERS)
        self._stopped = False

    def stop(self):
        self._stopped = True

    def _build(self, spec):
        self._pool.apply_async(build_app, spec)

    def run(self):
        while not self._stopped:
            next_job = build_queue.get()
            self._build(next_job)

