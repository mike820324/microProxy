import zmq
import json
import ConfigParser
import logging
logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def start_server():
    parser = ConfigParser.SafeConfigParser()
    parser.read("application.cfg")

    context = zmq.Context()
    socket = context.socket(zmq.REP)
    host = parser.get("ConnectionController", "zmq.host")
    port = parser.get("ConnectionController", "zmq.port")
    socket.bind("tcp://{0}:{1}".format(host, port))

    logger.info("zmq is listening at tcp://{0}:{1}".format(host, port))

    while True:
        data = socket.recv()
        message = json.loads(data)
        status = message["response"]["status"]
        method = message["request"]["method"]
        url = message["request"]["url"]
        logger.info("{0} {1} {2}".format(status, method, url))
        socket.send_json(message)
