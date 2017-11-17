#!/usr/bin/env python
import os
import time
import redis
import pickle


redis_connection = redis.from_url(os.environ['REDIS_URL'])


def queue_daemon(queue, rv_ttl=500):
    while 1:
        print('[daemon]: waiting for instruction...')
        msg = redis_connection.blpop(queue)
        print('[daemon]: received!')
        try:
            func, key, args, kwargs = pickle.loads(msg[1])
        except Exception, e:
            try:
                print(f'[daemon]: failed to unpickle {e}')
            except (TypeError, IndexError):
                pass
        else:
            try:
                print(f'[daemon]: calling {func.func_name}')
                rv = func(*args, **kwargs)
                print('[daemon]: complete!')
            except Exception, e:
                print(f'[daemon]: {e}')
                rv = e
            if rv is not None:
                redis_connection.set(key, pickle.dumps(rv))
                redis_connection.expire(key, rv_ttl)
                print(f'[daemon]: stored return value at {key}')
        print('[daemon]: sleeping for a bit...')
        time.sleep(0.25)


queue_daemon('deferred_queue')