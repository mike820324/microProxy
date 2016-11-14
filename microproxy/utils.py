import zmq
from zmq.eventloop import zmqstream
from zmq.eventloop.ioloop import IOLoop
from OpenSSL import SSL


try:
    HAS_ALPN = SSL._lib.Cryptography_HAS_ALPN
except:
    HAS_ALPN = False


def curr_loop():  # pragma: no cover
    return IOLoop.current()


def create_publish_channel(channel):  # pragma: no cover
    context = zmq.Context()
    socket = context.socket(zmq.PUB)
    socket.bind(channel)
    return socket


def create_event_channel(channel):  # pragma: no cover
    context = zmq.Context()
    socket = context.socket(zmq.PULL)
    socket.bind(channel)
    return zmqstream.ZMQStream(socket)
