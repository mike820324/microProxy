import platform
import struct
import datetime
import sys
from mock import Mock, PropertyMock, call
from tornado.concurrent import Future
import tornado.testing
from tornado.testing import AsyncTestCase
import tornado.gen

from microproxy import proxy


class SocksProxyHandlerTest(AsyncTestCase):
    def setUp(self):
        super(SocksProxyHandlerTest, self).setUp()
        self.handler = proxy.SocksProxyHandler()

    @tornado.testing.gen_test
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

    @tornado.testing.gen_test
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
        self.context = proxy.Context(Mock(), Mock(), Mock())
        self.http_layer = proxy.HttpLayer(self.context)

    @tornado.testing.gen_test
    def test_process_success(self):
        self.context.src_stream.read_bytes = Mock(return_value=_create_future(
            b"GET / HTTP/1.1\r\n" +
            b"host: github.com\r\n\r\n"))
        self.context.src_stream.write = Mock(return_value=_create_future(None))
        self.context.dest_stream.read_bytes = Mock(side_effect=[
            _create_future(
                b"HTTP/1.1 200 OK\r\n" +
                b"Content-Type: text/html\r\n\r\n" +
                b"<html></html>"),
            _create_future(b"")
        ])
        self.context.dest_stream.write = Mock(return_value=_create_future(None))

        self.context.interceptor.request = Mock()
        self.context.interceptor.response = Mock()
        self.context.interceptor.record = Mock()

        yield tornado.gen.with_timeout(datetime.timedelta(seconds=1), self.http_layer.process())
        self.context.src_stream.read_bytes.assert_called_with(sys.maxsize, partial=True)
        self.context.dest_stream.read_bytes.assert_called_with(sys.maxsize, partial=True)
        assert self.context.interceptor.request.called
        assert self.context.interceptor.response.called
        assert self.context.interceptor.record.called


def _create_future(result):
    future = Future()
    future.set_result(result)
    return future
