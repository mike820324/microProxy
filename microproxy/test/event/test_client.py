import mock
import unittest

from microproxy.context import Event
from microproxy.event import EventClient


class TestEventClient(unittest.TestCase):
    def setUp(self):
        self.zmq_socket = mock.Mock()
        self.event_client = EventClient(None, zmq_socket=self.zmq_socket)

    def test_send_event(self):
        self.event_client.send_event(Event(name="replay", context={"replay": "gogo"}))
        self.zmq_socket.send_json.assert_called_with({
            "name": "replay",
            "context": {
                "replay": "gogo"
            }
        })


if __name__ == "__main__":
    unittest.main()
