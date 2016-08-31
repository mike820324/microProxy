import mock
import unittest

from microproxy.event import EventClient


class TestEventClient(unittest.TestCase):
    def setUp(self):
        self.zmq_socket = mock.Mock()
        self.event_client = EventClient(None, zmq_socket=self.zmq_socket)

    def test_send_event(self):
        self.event_client.send_event(dict(event="yoyo"))
        self.zmq_socket.send_json.assert_called_with(dict(event="yoyo"))


if __name__ == "__main__":
    unittest.main()
