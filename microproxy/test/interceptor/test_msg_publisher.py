import json
import unittest
import mock

from microproxy.context import ViewerContext
from microproxy.interceptor.msg_publisher import MsgPublisher
from microproxy.version import VERSION


class TestMsgPublisher(unittest.TestCase):
    def setUp(self):
        self.zmq_socket = mock.Mock()
        self.msg_publisher = MsgPublisher(None, self.zmq_socket)

    def test_publish(self):
        ctx_data = {
            "scheme": "https",
            "host": "example.com",
            "path": "/index",
            "port": 443,
            "version": VERSION,
            "client_tls": None,
            "server_tls": None,
            "response": None,
            "request": None,
        }
        ctx = ViewerContext.deserialize(ctx_data)
        self.msg_publisher.publish(ctx)

        self.zmq_socket.send_multipart.assert_called_with([
            "message",
            JsonStrMatcher(ctx_data)])


class JsonStrMatcher(object):
    def __init__(self, data):
        self.data = data

    def __eq__(self, other):
        return json.loads(other) == self.data

    def __str__(self):
        return str(self.data)
