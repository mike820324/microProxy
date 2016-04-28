import zmq
import json

from microproxy.config import config
from microproxy.utils import get_logger

logger = get_logger(__name__)


def start():
    context = zmq.Context()
    socket = context.socket(zmq.SUB)
    destination = config.prop("ZmqClient", "zmq.destination")
    socket.connect(destination)
    socket.setsockopt(zmq.SUBSCRIBE, "")
    logger.info("zmq is listening at {0}".format(destination))

    while True:
        logger.debug("waiting for next message")
        data = socket.recv()
        message = json.loads(data)
        host = message["request"]["header"]["Host"]
        status = message["response"]["status"]
        method = message["request"]["method"]
        url = message["request"]["url"]
        logger.info("{0} {1} {2} {3}".format(host, status, method, url))
