import platform
import struct
from mock import Mock, PropertyMock, call
from tornado.concurrent import Future
from tornado.testing import AsyncTestCase, gen_test

from microproxy import proxy


class SocksProxyHandlerTest(AsyncTestCase):
    def setUp(self):
        super(SocksProxyHandlerTest, self).setUp()
        self.handler = proxy.SocksProxyHandler()

    @gen_test
    def test_read_and_return_addr(self):
        stream_source = Mock()
        stream_source.side_effect = [
            _create_future(struct.pack("BBB", 0x05, 0x01, 0x00)),
            _create_future(struct.pack("!BBxB", 0x05, 0x01, 0x01)),
            _create_future(struct.pack("!IH", 0x7F000001, 80))]
        stream = Mock()
        stream.read_bytes = stream_source
        socket = Mock()
        socket.getpeername = Mock(return_value=["127.0.0.1"])
        type(stream).socket = PropertyMock(return_value=socket)
        stream.write = Mock(return_value=_create_future(None))

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


class TranparentProxyHandlerTest(AsyncTestCase):
    def setUp(self):
        super(TranparentProxyHandlerTest, self).setUp()
        self.handler = proxy.TranparentProxyHandler()

    @gen_test
    def test_read_and_return_addr(self):
        if platform.system() == "Linux":
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


class HttpLayerTest(AsyncTestCase):
    def setUp(self):
        super(HttpLayerTest, self).setUp()


def _create_future(result):
    future = Future()
    future.set_result(result)
    return future
