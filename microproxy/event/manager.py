import zmq
from zmq.eventloop import zmqstream


from microproxy.utils import get_logger

logger = get_logger(__name__)


class EventManager(object):
    def __init__(self, config, proxy_server, zmq_stream=None):
        super(EventManager, self).__init__()
        self.proxy_server = proxy_server
        self.zmq_stream = zmq_stream or self._create_stream(config)
        self._start()

    def _create_stream(self, config):
        context = zmq.Context()
        socket = context.socket(zmq.PULL)
        socket.bind(config["events_channel"])
        logger.info("EventManager is listening at {0}".format(config["events_channel"]))
        return zmqstream.ZMQStream(socket)

    def _start(self):
        self.zmq_stream.on_recv(self._on_recv)

    def _on_recv(self, msg_parts):
        event = msg_parts[0]
        logger.info("Receive event: {0}".format(event))
