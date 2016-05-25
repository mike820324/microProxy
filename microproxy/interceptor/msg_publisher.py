import zmq
from zmq.eventloop import zmqstream

from microproxy.utils import get_logger

logger = get_logger(__name__)


class MsgPublisher(object):
    def __init__(self, config, zmq_socket=None):
        super(MsgPublisher, self).__init__()
        if zmq_socket is None:
            zmq_socket = self.create_socket(config["viewer_channel"])
        self.zmq_stream = zmqstream.ZMQStream(zmq_socket)

    def create_socket(self, viewer_channel):
        context = zmq.Context()
        socket = context.socket(zmq.PUB)
        socket.bind(viewer_channel)
        logger.info("MsgPublisher is listening at {0}".format(viewer_channel))
        return socket

    def publish(self, request, response):
        message = {
            "request": request.serialize(),
            "response": response.serialize()
        }
        self.zmq_stream.send_json(message)
