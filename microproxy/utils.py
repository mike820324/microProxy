import zmq
from zmq.eventloop import zmqstream
from zmq.log.handlers import PUBHandler
from zmq.eventloop.ioloop import IOLoop
import logging
import logging.config

logging.config.fileConfig('logging.cfg')


def curr_loop():  # pragma: no cover
    return IOLoop.current()


def get_logger(name):
    short_name = ".".join(name.split(".")[1:])
    return logging.getLogger(short_name)


def create_publish_channel(channel):  # pragma: no cover
    context = zmq.Context()
    socket = context.socket(zmq.PUB)
    socket.bind(channel)
    return socket


def register_log_publisher(socket):  # pragma: no cover
    handler = PUBHandler(socket)
    handler.root_topic = "logger"
    logger = logging.getLogger()
    logger.addHandler(handler)


def create_event_channel(channel):  # pragma: no cover
    context = zmq.Context()
    socket = context.socket(zmq.PULL)
    socket.bind(channel)
    return zmqstream.ZMQStream(socket)
