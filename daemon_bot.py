#!/usr/bin/env python
import os
import redis
import pickle

from app import QUEUE_NAME


redis_connection = redis.from_url(os.environ["REDIS_URL"])


def queue_daemon(queue, rv_ttl=500):
    while 1:
        msg = redis_connection.blpop(queue)
        func, key, args, kwargs = pickle.loads(msg[1])
        try:
            rv = func(*args, **kwargs)
        except Exception, e:
            rv = e
        if rv is not None:
            redis_connection.set(key, pickle.dumps(rv))
            redis_connection.expire(key, rv_ttl)


queue_daemon(QUEUE_NAME)