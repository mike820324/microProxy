import zmq
from zmq.eventloop import zmqstream
import logging

from config import Config


class MsgPublisher(object):
    def __init__(self, zmq_socket):
        self.zmq_stream = zmqstream.ZMQStream(zmq_socket)
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)

    def publish(self, message):
        self.zmq_stream.send_json(message)


def create():
    config = Config()
    binding = config.prop("ZmqServer", "zmq.binding")
    context = zmq.Context()
    socket = context.socket(zmq.PUB)
    socket.bind(binding)
    logging.info("MsgPublisher is listening at {0}".format(binding))
    return MsgPublisher(socket)
