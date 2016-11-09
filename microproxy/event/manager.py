import json

from microproxy.context import Event
from microproxy.utils import get_logger
from replay import ReplayHandler
from types import REPLAY

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
            event = Event.deserialize(json.loads(message))
        except:
            logger.error("Wrong message received: {0}".format(message))
        else:
            logger.debug("Receive event: {0}".format(event))
            try:
                self.handler.handle_event(event)
            except Exception as e:
                logger.error("handle event failed: {0}".format(e))


class EventHandler(object):
    def __init__(self, server_state):
        self.handlers = {
            REPLAY: ReplayHandler(server_state)
        }

    def handle_event(self, event):
        if event.name in self.handlers:
            self.handlers[event.name].handle(event)
        else:
            logger.error("Unhandled event: {0}".format(event.name))


def start_events_server(server_state, zmq_stream):
    EventManager(server_state, zmq_stream).start()
