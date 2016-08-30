import zmq
from zmq.eventloop import zmqstream

import json

from microproxy.utils import get_logger
from replay import ReplayHandler

logger = get_logger(__name__)


class EventManager(object):
    def __init__(self, config, handler=None, zmq_stream=None):
        super(EventManager, self).__init__()
        self.handler = handler or EventHandler(config)
        self.zmq_stream = zmq_stream or self._create_stream(config)

    def start(self):
        self.zmq_stream.on_recv(self._on_recv)

    def _create_stream(self, config):  # pragma: no cover
        context = zmq.Context()
        socket = context.socket(zmq.PULL)
        socket.bind(config["events_channel"])
        logger.info("EventManager is listening at {0}".format(config["events_channel"]))
        return zmqstream.ZMQStream(socket)

    def _on_recv(self, msg_parts):
        message = msg_parts[0]
        try:
            event = json.loads(message)
        except:
            logger.error("Wrong message received: {0}".format(message))
        else:
            logger.debug("Receive event: {0}".format(event))
            self.handler.handle_event(event)


class EventHandler(object):
    def __init__(self, config):
        self.config = config
        self.handler = ReplayHandler(self.config)

    def handle_event(self, event):
        self.handler.handle(event)


def start_events_server(config):
    EventManager(config).start()
