from zmq.eventloop.ioloop import IOLoop
import logging
import logging.config

logging.config.fileConfig('logging.cfg')


def curr_loop():
    return IOLoop.current()


def get_logger(name):
    return logging.getLogger(name)
