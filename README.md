# Oxen Observer OMG block explorer

Block explorer using Oxen 8+ LMQ RPC interface that does everything through RPC requests.  Sexy,
awesome, safe.

## Prerequisite packages 

    sudo apt install build-essential pkg-config libsodium-dev libzmq3-dev python3-dev python3-flask python3-babel python3-pygments python3-oxenmq python3-pycryptodome python3-nacl python3-pysodium python3-qrcode

Note that the last requirement (python3-oxenmq) comes from the Oxen repository (https://deb.oxen.io).

## Running in debug mode

To run it in debug mode (production requires setting up a WSGI server, see below):

    FLASK_APP=observer flask run --reload --debugger

This mode seems to be a bit flakey, though -- reloading, in particular, seems to break things and
make it just silently exit after a while, so only do this for quick and dirty testing.

## Setting up for production with uwsgi-emperor:

Do the above, but instead of running it with flask directly, set up uwsgi-emperor as follows:

    apt install uwsgi-emperor uwsgi-plugin-python3

in `/etc/uwsgi-emperor/emperor.ini` add configuration of:

    # vassals directory
    emperor = /etc/uwsgi-emperor/vassals
    cap = setgid,setuid
    emperor-tyrant = true

Create a "vassal" config for oxen-observer, `/etc/uwsgi-emperor/vassals/oxen-observer.ini`, containing:

    [uwsgi]
    chdir = /path/to/oxen-observer
    socket = mainnet.wsgi
    plugins = python3,logfile
    processes = 4
    manage-script-name = true
    mount = /=mainnet:app

    logger = file:logfile=/path/to/oxen-observer/mainnet.log

Set ownership of this user to whatever user you want it to run as, and set the group to `_loki` (so
that it can open the oxend unix socket):

    chown MYUSERNAME:_loki /etc/uwsgi-emperor/vassals/oxen-observer.ini

In the oxen-observer/mainnet.py, set:

    config.oxend_rpc = 'ipc:///var/lib/oxen/oxend.sock'

and finally, proxy requests from the webserver to the wsgi socket.  For Apache I do this with:

    # Allow access to static files (e.g. .css and .js):
    <Directory /path/to/oxen-observer/static>
        Require all granted
    </Directory>
    DocumentRoot /home/jagerman/src/oxen-observer/static

    # Proxy everything else via the uwsgi socket:
    ProxyPassMatch "^/[^/]*\.(?:css|js)(?:$|\?)" !
    ProxyPass / unix:/path/to/oxen-observer/mainnet.wsgi|uwsgi://uwsgi-mainnet-observer/

(you will probably need to `a2enmod proxy_uwsgi` to enable the Apache modules that make that work).

That should be it: restart apache2 and uwsgi-emperor and you should be good to go.  If you want to
make uwsgi restart (for example because you are changing things) then it is sufficient to `touch
/etc/uwsgi-emperor/vassals/oxen-observer.ini` to trigger a reload (you do not have to restart the
apache2/uwsgi-emperor layers).

If you want to set up a testnet or devnet observer the procedure is essentially the same, but
using testnet.py or devnet.py pointing to the oxend.sock from a testnet or devnet oxend.
