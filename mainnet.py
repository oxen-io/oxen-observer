from observer import app, config
import oxenmq

config.oxend_rpc = oxenmq.Address('ipc://oxend/mainnet.sock')
