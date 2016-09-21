import json

from microproxy.utils import get_logger
from replay import ReplayHandler

logger = get_logger(__name__)


class EventManager(object):
    def __init__(self, server_state, zmq_stream, handler=None):
        super(EventManager, self).__init__()
        self.handler = handler or EventHandler(server_state)
        self.zmq_stream = zmq_stream

    def start(self):
        self.zmq_stream.on_recv(self._on_recv)

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
    def __init__(self, server_state):
        self.handler = ReplayHandler(server_state)

    def handle_event(self, event):
        self.handler.handle(event)


def start_events_server(server_state, zmq_stream):
    EventManager(server_state, zmq_stream).start()
