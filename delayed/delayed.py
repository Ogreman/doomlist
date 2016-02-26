import os
import redis
import uuid

from flask import current_app
from pickle import loads, dumps


redis_connection = redis.from_url(os.environ["REDIS_URL"])


class DelayedResult(object):
    def __init__(self, key):
        self.key = key
        self._return_value = None

    # @property
    # def return_value(self):
    #     if self._return_value is None:
    #         rv = redis_connection.get(self.key)
    #         if rv is not None:
    #             self._return_value = loads(rv)
    #     return self._return_value


def queue_func(f):
    def delay(*args, **kwargs):
        qkey = current_app.config['REDIS_QUEUE_KEY']
        key = '%s:result:%s' % (qkey, str(uuid.uuid4()))
        s = dumps((f, key, args, kwargs))
        redis_connection.rpush(qkey, s)
        return DelayedResult(key)
    f.delay = delay
    return f



