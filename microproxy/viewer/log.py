import zmq
import json

from microproxy.utils import get_logger

logger = get_logger(__name__)


def start(config):
    context = zmq.Context()
    socket = context.socket(zmq.SUB)
    destination = config["viewer_channel"]
    socket.connect(destination)
    socket.setsockopt(zmq.SUBSCRIBE, "")
    logger.info("zmq is listening at {0}".format(destination))

    while True:
        logger.debug("waiting for next message")
        data = socket.recv()
        message = json.loads(data)
        host = message["request"]["headers"]["Host"]
        status = message["response"]["code"]
        method = message["request"]["method"]
        url = message["request"]["path"]
        logger.info("{0} {1} {2} {3}".format(host, status, method, url))
