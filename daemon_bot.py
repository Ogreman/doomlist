#!/usr/bin/env python
import os
import redis
import pickle


redis_connection = redis.from_url(os.environ["REDIS_URL"])


def queue_daemon(queue, rv_ttl=500):
    while 1:
        print "[daemon]: waiting for instruction..."
        msg = redis_connection.blpop(queue)
        print "[daemon]: received!"
        try:
            func, key, args, kwargs = pickle.loads(msg[1])
        except Exception, e:
            try:
                print "[daemon]: failed to unpickle %s" % msg[1]
            except (TypeError, IndexError):
                pass
        else:
            try:
                print "[daemon]: calling %s" % func
                rv = func(*args, **kwargs)
                print "[daemon]: complete!"
            except Exception, e:
                print "[daemon]: %s" % e
                rv = e
            if rv is not None:
                redis_connection.set(key, pickle.dumps(rv))
                redis_connection.expire(key, rv_ttl)
                print "[daemon]: stored return value at %s" % key


queue_daemon("deferred_queue")