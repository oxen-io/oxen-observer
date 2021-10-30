import oxenmq
import config
import json
import sys
from datetime import datetime, timedelta

omq, oxend = None, None
def omq_connection():
    global omq, oxend
    if omq is None:
        omq = oxenmq.OxenMQ(log_level=oxenmq.LogLevel.warn)
        omq.max_message_size = 200*1024*1024
        omq.start()
    if oxend is None:
        oxend = omq.connect_remote(config.oxend_rpc)
    return (omq, oxend)

cached = {}
cached_args = {}
cache_expiry = {}

class FutureJSON():
    """Class for making a LMQ JSON RPC request that uses a future to wait on the result, and caches
    the results for a set amount of time so that if the same endpoint with the same arguments is
    requested again the cache will be used instead of repeating the request.

    Cached values are indexed by endpoint and optional key, and require matching arguments to the
    previous call.  The cache_key should generally be a fixed value (*not* an argument-dependent
    value) and can be used to provide multiple caches for different uses of the same endpoint.
    Cache entries are *not* purged, they are only replaced, so using dynamic data in the key would
    result in unbounded memory growth.

    omq - the omq object
    oxend - the oxend omq connection id object
    endpoint - the omq endpoint, e.g. 'rpc.get_info'
    cache_seconds - how long to cache the response; can be None to not cache it at all
    cache_key - fixed string to enable different caches of the same endpoint
    args - if not None, a value to pass (after converting to JSON) as the request parameter. Typically a dict.
    fail_okay - can be specified as True to make failures silent (i.e. if failures are sometimes expected for this request)
    timeout - maximum time to spend waiting for a reply
    """

    def __init__(self, omq, oxend, endpoint, cache_seconds=3, *, cache_key='', args=None, fail_okay=False, timeout=10):
        self.endpoint = endpoint
        self.cache_key = self.endpoint + cache_key
        self.fail_okay = fail_okay
        if args is not None:
            args = json.dumps(args).encode()
        if self.cache_key in cached and cached_args[self.cache_key] == args and cache_expiry[self.cache_key] >= datetime.now():
            self.json = cached[self.cache_key]
            self.args = None
            self.future = None
        else:
            self.json = None
            self.args = args
            self.future = omq.request_future(oxend, self.endpoint, [] if self.args is None else [self.args], timeout=timeout)
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
                if self.cache_seconds is not None:
                    cached[self.cache_key] = self.json
                    cached_args[self.cache_key] = self.args
                    cache_expiry[self.cache_key] = datetime.now() + timedelta(seconds=self.cache_seconds)
            except RuntimeError as e:
                if not self.fail_okay:
                    print("Something getting wrong: {}".format(e), file=sys.stderr)
                self.future = None

        return self.json


