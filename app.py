#!/usr/bin/env python3

import flask
import pylokimq
from datetime import datetime, timedelta
import babel.dates
import json
import sys
import statistics

app = flask.Flask(__name__)
# DEBUG:
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.jinja_env.auto_reload = True
# end DEBUG

lmq = pylokimq.LokiMQ(pylokimq.LogLevel.warn)
lmq.max_message_size = 10*1024*1024
lmq.start()
lokid = lmq.connect_remote('ipc://./mainnet.sock')
#lokid = lmq.connect_remote('ipc://./testnet.sock')
#lokid = lmq.connect_remote('ipc://./devnet.sock')

cached = {}
cached_args = {}
cache_expiry = {}

class FutureJSON():
    def __init__(self, endpoint, cache_seconds=3, *, args=[], fail_okay=False, timeout=10):
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
                if result[0] != b'200':
                    raise RuntimeError("Request failed: got {}".format(result))
                self.json = json.loads(result[1])
                cached[self.endpoint] = self.json
                cached_args[self.endpoint] = self.args
                cache_expiry[self.endpoint] = datetime.now() + timedelta(seconds=self.cache_seconds)
            except RuntimeError as e:
                if not self.fail_okay:
                    print("Something getting wrong: {}".format(e), file=sys.stderr)
                self.future = None
                pass

        return self.json


@app.template_filter('format_datetime')
def format_datetime(value, format='long'):
    return babel.dates.format_datetime(value, format, tzinfo=babel.dates.get_timezone('UTC'))

@app.template_filter('from_timestamp')
def from_timestamp(value):
    return datetime.fromtimestamp(value)

@app.template_filter('ago')
def datetime_ago(value):
    delta = datetime.now() - value
    disp=''
    if delta.days < 0:
        delta = -delta
        disp += '-'
    if delta.days > 0:
        disp += '{}d '.format(delta.days)
    disp += '{:2d}:{:02d}:{:02d}'.format(delta.seconds // 3600, delta.seconds // 60 % 60, delta.seconds % 60)
    return disp

@app.template_filter('round')
def filter_round(value):
    return ("{:.0f}" if value >= 100 or isinstance(value, int) else "{:.1f}" if value >= 10 else "{:.2f}").format(value)

si_suffix = ['', 'k', 'M', 'G', 'T', 'P', 'E', 'Z', 'Y']
@app.template_filter('si')
def format_si(value):
    i = 0
    while value >= 1000 and i < len(si_suffix) - 1:
        value /= 1000
        i += 1
    return filter_round(value) + '{}'.format(si_suffix[i])

@app.template_filter('loki')
def format_loki(atomic, tag=True, fixed=False, decimals=9):
    """Formats an atomic current value as a human currency value.
    tag - if False then don't append " LOKI"
    fixed - if True then don't strip insignificant trailing 0's and '.'
    decimals - at how many decimal we should round; the default is full precision
    """
    disp = "{{:.{}f}}".format(decimals).format(atomic * 1e-9)
    if not fixed:
        disp = disp.rstrip('0').rstrip('.')
    if tag:
        disp += ' LOKI'
    return disp

@app.after_request
def add_global_headers(response):
    if 'Cache-Control' not in response.headers:
        response.headers['Cache-Control'] = 'no-store'
    return response

@app.route('/style.css')
def css():
    return flask.send_from_directory('static', 'style.css')

@app.route('/')
@app.route('/page/<int:page>')
@app.route('/page/<int:page>/<int:per_page>')
@app.route('/range/<int:first>/<int:last>')
@app.route('/autorefresh/<int:refresh>')
def main(refresh=None, page=0, per_page=None, first=None, last=None):
    info = FutureJSON('rpc.get_info', 1)
    stake = FutureJSON('rpc.get_staking_requirement', 10)
    base_fee = FutureJSON('rpc.get_fee_estimate', 10)
    hfinfo = FutureJSON('rpc.hard_fork_info', 10)
    mempool = FutureJSON('rpc.get_transaction_pool', 5)
    # This call is slow the first time it gets called in lokid but will be fast after that, so call
    # it with a very short timeout.  It's also an admin-only command, so will always fail if we're
    # using a restricted RPC interface.
    coinbase = FutureJSON('admin.get_coinbase_tx_sum', 10, timeout=1, fail_okay=True,
            args=[json.dumps({"height":0, "count":2**31-1}).encode()])
    server = dict(
            timestamp=datetime.utcnow(),
            )

    config = dict(
            # FIXME: make these configurable
            pusher=True,
            key_image_checker=True,
            output_key_checker=True,
            autorefresh_option=True,
            mainnet_url='',
            testnet_url='',
            devnet_url='',
            blocks_per_page=20
            )

    custom_per_page = ''
    if per_page is None or per_page <= 0 or per_page > 100:
        per_page = config['blocks_per_page']
    else:
        custom_per_page = '/{}'.format(per_page)

    # We have some chained request dependencies here and below, so get() them as needed; all other
    # non-dependent requests should already have a future initiated above so that they can
    # potentially run in parallel.
    height = info.get()['height']

    # Permalinked block range:
    if first is not None and last is not None and 0 <= first <= last and last <= first + 99:
        start_height, end_height = first, last
        if end_height - start_height + 1 != per_page:
            per_page = end_height - start_height + 1;
            custom_per_page = '/{}'.format(per_page)
        # We generally can't get a perfect page number because our range (e.g. 5-14) won't line up
        # with pages (e.g. 10-19, 0-19), so just get as close as we can.  Next/Prev page won't be
        # quite right, but they'll be within half a page.
        page = round((height - 1 - end_height) / per_page)
    else:
        end_height = max(0, height - per_page*page - 1)
        start_height = max(0, end_height - per_page + 1)

    blocks = FutureJSON('rpc.get_block_headers_range', args=[json.dumps({
        'start_height': start_height,
        'end_height': end_height,
        'get_tx_hashes': True,
        }).encode()]).get()['headers']

    # If 'txs' is already there then it is probably left over from our cached previous call through
    # here.
    if blocks and 'txs' not in blocks[0]:
        txids = []
        for b in blocks:
            b['txs'] = []
            txids.append(b['miner_tx_hash'])
            if 'tx_hashes' in b:
                txids += b['tx_hashes']
        txs = FutureJSON('rpc.get_transactions', args=[json.dumps({
            "txs_hashes": txids,
            "decode_as_json": True,
            "tx_extra": True,
            "prune": True,
            }).encode()]).get()
        txs = txs['txs']
        i = 0
        for tx in txs:
            # TXs should come back in the same order so we can just skip ahead one when the block
            # height changes rather than needing to search for the block
            if blocks[i]['height'] != tx['block_height']:
                i += 1
                while i < len(blocks) and blocks[i]['height'] != tx['block_height']:
                    print("Something getting wrong: missing txes?", file=sys.stderr)
                    i += 1
                if i >= len(blocks):
                    print("Something getting wrong: have leftover txes")
                    break
            tx['info'] = json.loads(tx['as_json'])
            blocks[i]['txs'].append(tx)


    #txes = FutureJSON('rpc.get_transactions');


    # mempool RPC return values are about as nasty as can be.  For each mempool tx, we get back
    # *both* binary+hex encoded values and JSON-encoded values slammed into a string, which means we
    # have to invoke an *extra* JSON parser for each tx.  This is terrible.
    mp = mempool.get()
    if 'transactions' in mp:
        for tx in mp['transactions']:
            tx['info'] = json.loads(tx["tx_json"])
    else:
        mp['transactions'] = []

    return flask.render_template('index.html',
            info=info.get(),
            stake=stake.get(),
            fees=base_fee.get(),
            emission=coinbase.get(),
            hf=hfinfo.get(),
            blocks=blocks,
            block_size_median=statistics.median(b['block_size'] for b in blocks),
            page=page,
            per_page=per_page,
            custom_per_page=custom_per_page,
            mempool=mp,
            server=server,
            config=config,
            refresh=refresh,
            )
