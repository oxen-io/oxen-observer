# Loki Observer OMG block explorer

Block explorer using Loki 8+ LMQ RPC interface that does everything through RPC requests.  Sexy,
awesome, safe.

## Building and running

Quick and dirty setup instructions for now:

    git submodule update --init --recursive
    cd pylokimq
    mkdir build
    cd build
    cmake ..
    make -j6
    cd ../..
    ln -s pylokimq/build/pylokimq/pylokimq.cpython-*.so .
    sudo apt install python3-flask python3-babel

(Note that we require a very recent python3-jinja package (2.11+), which may not be installed by the
above.)

You'll also need to run lokid with `--lmq-local-control ipc:///path/to/loki-observer/mainnet.sock`.

Then to run it in debug mode (production requires setting up a WSGI server, will document layer):

    flask run --reload --debugger

This mode seems to be a bit flakey -- reloading, in particular, seems to break things and make it
just silently exit after a while.
