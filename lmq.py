import pylokimq
import config
import json
import sys
from datetime import datetime, timedelta

lmq, lokid = None, None
def lmq_connection():
    global lmq, lokid
    if lmq is None:
        lmq = pylokimq.LokiMQ(pylokimq.LogLevel.warn)
        lmq.max_message_size = 10*1024*1024
        lmq.start()
    if lokid is None:
        lokid = lmq.connect_remote(config.lokid_rpc)
    return (lmq, lokid)

cached = {}
cached_args = {}
cache_expiry = {}

class FutureJSON():
    """Class for making a LMQ JSON RPC request that uses a future to wait on the result, and caches
    the results for a set amount of time so that if the same endpoint with the same arguments is
    requested again the cache will be used instead of repeating the request."""

    def __init__(self, lmq, lokid, endpoint, cache_seconds=3, *, args=[], fail_okay=False, timeout=10):
        self.endpoint = endpoint
        self.fail_okay = fail_okay
        if self.endpoint in cached and cached_args[self.endpoint] == args and cache_expiry[self.endpoint] >= datetime.now():
            self.json = cached[self.endpoint]
            self.args = None
            self.future = None
        else:
            self.json = None
            self.args = args
            self.future = lmq.request_future(lokid, self.endpoint, self.args, timeout=timeout)
        self.cache_seconds = cache_seconds

    def get(self):
        """If the result is already available, returns it immediately (and can safely be called multiple times.
        Otherwise waits for the result, parses as json, and caches it.  Returns None if the request fails"""
        if self.json is None and self.future is not None:
            try:
                result = self.future.get()
                self.future = None
                if result[0] != b'200':
                    raise RuntimeError("Request for {} failed: got {}".format(self.endpoint, result))
                self.json = json.loads(result[1])
                cached[self.endpoint] = self.json
                cached_args[self.endpoint] = self.args
                cache_expiry[self.endpoint] = datetime.now() + timedelta(seconds=self.cache_seconds)
            except RuntimeError as e:
                if not self.fail_okay:
                    print("Something getting wrong: {}".format(e), file=sys.stderr)
                self.future = None

        return self.json


