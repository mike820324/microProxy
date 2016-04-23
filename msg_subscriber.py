import zmq
import json

from config import Config
import logging

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def start():
    context = zmq.Context()
    socket = context.socket(zmq.SUB)
    config = Config()
    destination = config.prop("ZmqClient", "zmq.destination")
    socket.connect(destination)
    socket.setsockopt(zmq.SUBSCRIBE, "")
    logger.info("zmq is listening at {0}".format(destination))

    while True:
        logger.debug("waiting for next message")
        data = socket.recv()
        message = json.loads(data)
        status = message["response"]["status"]
        method = message["request"]["method"]
        url = message["request"]["url"]
        logger.info("{0} {1} {2}".format(status, method, url))
