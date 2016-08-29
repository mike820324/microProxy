import zmq


from microproxy.utils import get_logger

logger = get_logger(__name__)


class EventClient(object):
    def __init__(self, config, zmq_socket=None):
        super(EventClient, self).__init__()
        self.zmq_socket = zmq_socket or self._create_socket(config)

    def _create_socket(self, config):  # pragma: no cover
        context = zmq.Context()
        socket = context.socket(zmq.PUSH)
        socket.connect(config["events_channel"])
        logger.info("EventClient is connect to {0}".format(config["events_channel"]))
        return socket

    def send_event(self, event):
        self.zmq_socket.send_json(event)
