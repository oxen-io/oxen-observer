# Default configuration options for block observer.
#
# To override settings add `config.whatever = ...` into `local_config.py`; adding settings *here*
# will often cause git conflicts.
#
# To override things that are specific to mainnet/testnet/etc. add `config.whatever = ...` lines
# into `mainnet.py`/`testnet.py`/etc.


# LMQ RPC endpoint of lokid; can be a unix socket 'ipc:///path/to/lokid.sock' (preferred) or a tcp
# socket 'tcp://127.0.0.1:5678'.  Typically you want this running with admin permission.
# Leave this as None here, and set it for each observer in the mainnet.py/testnet.py/etc. script.
lokid_rpc = None

# Default blocks per page for the index.
blocks_per_page=20
# Maximum blocks per page a user can request
max_blocks_per_page=100

# Some display and/or feature options:
pusher=False
key_image_checker=False
output_key_checker=False
autorefresh_option=True
enable_mixins_details=True

# URLs to networks other than the one we are on:
mainnet_url='https://blocks.lokinet.dev'
testnet_url='https://testnet.lokinet.dev'
devnet_url='https://devnet.lokinet.dev'

# Same as above, but these apply if we are on a .loki URL:
lokinet_mainnet_url='http://blocks.loki'
lokinet_testnet_url='http://testnet.loki'
lokinet_devnet_url='http://devnet.kcpyawm9se7trdbzncimdi5t7st4p5mh9i1mg7gkpuubi4k4ku1y.loki'
