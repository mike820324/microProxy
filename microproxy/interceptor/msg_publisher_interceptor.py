import zmq
from zmq.eventloop import zmqstream

from base import BaseInterceptor
from microproxy.http import serialize
from microproxy.utils import get_logger

logger = get_logger(__name__)


class MsgPublisherInterceptor(BaseInterceptor):
    def __init__(self, config, zmq_socket=None):
        super(MsgPublisherInterceptor, self).__init__()
        if zmq_socket is None:
            zmq_socket = create_socket(config["viewer_channel"])
        self.zmq_stream = zmqstream.ZMQStream(zmq_socket)

    def request(self, request):
        pass

    def response(self, response):
        pass

    def record(self, request, response):
        message = {
            "request": serialize(request),
            "response": serialize(response)
        }
        self._publish(message)

    def _publish(self, message):
        self.zmq_stream.send_json(message)


def create_socket(viewer_channel):
    context = zmq.Context()
    socket = context.socket(zmq.PUB)
    socket.bind(viewer_channel)
    logger.info("MsgPublisher is listening at {0}".format(viewer_channel))
    return socket
