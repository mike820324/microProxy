import json
import mock
import unittest

from microproxy.context import Event
from microproxy.event import EventManager


class TestEventManager(unittest.TestCase):
    def setUp(self):
        self.handler = mock.Mock()
        self.zmq_stream = mock.Mock()

        self.event_manager = EventManager(
            None, handler=self.handler, zmq_stream=self.zmq_stream)
        self.event_manager.start()

    def test_register_stream_call_invoked(self):
        self.zmq_stream.on_recv.assert_called_with(self.event_manager._on_recv)

    def test_recv(self):
        msg = json.dumps({
            "name": "replay",
            "context": {
                "replay": "yoyo"
            }
        })
        self.event_manager._on_recv([msg])
        self.handler.handle_event.assert_called_with(
            Event(name="replay", context={"replay": "yoyo"}))

if __name__ == "__main__":
    unittest.main()
