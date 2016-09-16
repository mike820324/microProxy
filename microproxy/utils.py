import zmq
from zmq.eventloop import zmqstream
from zmq.log.handlers import PUBHandler
from zmq.eventloop.ioloop import IOLoop
from OpenSSL import SSL

import logging
import logging.config


try:
    HAS_ALPN = SSL._lib.Cryptography_HAS_ALPN
except:
    HAS_ALPN = False


def init_system_logger():
    logging.config.fileConfig('logging.cfg')


def curr_loop():  # pragma: no cover
    return IOLoop.current()


def get_logger(name=None):  # pragma: no cover
    if name:
        short_name = ".".join(name.split(".")[1:])
        return logging.getLogger(short_name)

    return logging.getLogger()


def create_publish_channel(channel):  # pragma: no cover
    context = zmq.Context()
    socket = context.socket(zmq.PUB)
    socket.bind(channel)
    return socket


def register_log_publisher(socket, logger):  # pragma: no cover
    handler = PUBHandler(socket)
    handler.root_topic = "logger"
    logger.addHandler(handler)


def create_event_channel(channel):  # pragma: no cover
    context = zmq.Context()
    socket = context.socket(zmq.PULL)
    socket.bind(channel)
    return zmqstream.ZMQStream(socket)
