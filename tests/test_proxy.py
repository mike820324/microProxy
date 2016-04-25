import unittest
import struct
from mock import Mock, PropertyMock, call
from tornado.concurrent import Future
import tornado.gen

from microproxy import proxy


class SocksProxyHandlerTest(unittest.TestCase):
    def setUp(self):
        self.handler = proxy.SocksProxyHandler()

    @tornado.gen.coroutine
    def test_read_and_return_addr(self):
        stream_source = Mock()
        stream_source.side_effect = [
            self._create_future(struct.pack("BBB", 0x05, 0x01, 0x00)),
            self._create_future(struct.pack("!BBxB", 0x05, 0x01, 0x01)),
            self._create_future(struct.pack("!IH", 0x7F000001, 80))]
        stream = Mock()
        stream.read_bytes = stream_source
        socket = Mock()
        socket.getpeername = Mock(return_value=["127.0.0.1"])
        type(stream).socket = PropertyMock(return_value=socket)
        stream.write = Mock(return_value=self._create_future(""))

        addr_host, addr_port = yield self.handler.read_and_return_addr(stream)

        assert addr_host == "127.0.0.1"
        assert addr_port == 80

        stream_source.assert_has_calls([
            call(3),
            call(4),
            call(6)
        ])
        stream.write.assert_has_calls([
            call(struct.pack("BB", 0x05, 0)),
            call(struct.pack("!BBxBIH", 0x05, 0x00, 0x01, 0x7F000001, 80))
        ])

    def _create_future(self, result):
        future = Future()
        future.set_result(result)
        return future


class TranparentProxyHandlerTest(unittest.TestCase):
    def setUp(self):
        self.handler = proxy.TranparentProxyHandler()

    @tornado.gen.coroutine
    def test_read_and_return_addr(self):
        socket = Mock()
        socket.getsockopt = Mock(return_value=struct.pack(
            "!HHBBBBxxxxxxxx",
            0,
            80,
            0x7F,
            0x00,
            0x00,
            0x01))
        stream = Mock()
        type(stream).socket = PropertyMock(return_value=socket)
        addr_host, addr_port = yield self.handler.read_and_return_addr(stream)
        assert addr_host == "127.0.0.1"
        assert addr_port == 80
