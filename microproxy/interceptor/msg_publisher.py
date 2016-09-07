import zmq
import json

from microproxy.utils import get_logger

logger = get_logger(__name__)


class MsgPublisher(object):
    TOPIC = "message"

    def __init__(self, config, zmq_socket=None):
        super(MsgPublisher, self).__init__()
        self.zmq_socket = zmq_socket or self._create_socket(config["viewer_channel"])

    def _create_socket(self, viewer_channel):
        context = zmq.Context()
        socket = context.socket(zmq.PUB)
        socket.bind(viewer_channel)
        logger.info("MsgPublisher is listening at {0}".format(viewer_channel))
        return socket

    def publish(self, viewer_context):
        message = json.dumps(viewer_context.serialize())
        self.zmq_socket.send_multipart([
            self.TOPIC, message])
