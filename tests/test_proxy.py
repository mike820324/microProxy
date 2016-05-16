import platform
import struct
import socket

from tornado.concurrent import Future
from tornado.testing import AsyncTestCase, gen_test, bind_unused_port
from tornado.locks import Event
from tornado.iostream import IOStream
from tornado.netutil import add_accept_handler

from microproxy.proxy import SocksProxyHandler, TranparentProxyHandler


class SocksProxyHandlerTest(AsyncTestCase):
    def setUp(self):
        super(SocksProxyHandlerTest, self).setUp()
        self.handler = SocksProxyHandler()
        self.asyncSetUp()

    @gen_test
    def asyncSetUp(self):
        listener, port = bind_unused_port()
        event = Event()

        def accept_callback(conn, addr):
            self.server_stream = IOStream(conn)
            self.addCleanup(self.server_stream.close)
            event.set()
        add_accept_handler(listener, accept_callback)
        self.client_stream = IOStream(socket.socket())
        self.addCleanup(self.client_stream.close)
        yield [self.client_stream.connect(('127.0.0.1', port)),
               event.wait()]
        self.io_loop.remove_handler(listener)
        listener.close()

    @gen_test
    def test_read_and_return_ipv4_addr(self):
        addr_future = self.handler.read_and_return_addr(self.server_stream)
        yield self.client_stream.write(struct.pack("BBB", 0x05, 0x01, 0x00))
        data = yield self.client_stream.read_bytes(2)
        socks_version, _ = struct.unpack("BB", data)
        assert socks_version == 5

        yield self.client_stream.write(struct.pack("!BBxBIH", 0x05, 0x01, 0x01, 0x7F000001, 80))
        data = yield self.client_stream.read_bytes(10)
        socks_version, resp_status, addr_type, host, port = struct.unpack("!BBxBIH", data)
        assert socks_version == 5
        assert resp_status == 0
        assert addr_type == 1
        assert host == 0x7F000001
        assert port == 80

        host, port = yield addr_future
        self.server_stream.close()
        assert host == "127.0.0.1"
        assert port == 80

    @gen_test
    def test_read_and_return_host_addr(self):
        addr_future = self.handler.read_and_return_addr(self.server_stream)
        yield self.client_stream.write(struct.pack("BBB", 0x05, 0x01, 0x00))
        data = yield self.client_stream.read_bytes(2)
        socks_version, _ = struct.unpack("BB", data)
        assert socks_version == 5

        yield self.client_stream.write(struct.pack("!BBxBB21sH", 0x05, 0x01, 0x03, 0x15, "mike820324.github.com", 80))
        data = yield self.client_stream.read_bytes(28)
        socks_version, resp_status, addr_type, host, port = struct.unpack("!BBxBx21sH", data)
        assert socks_version == 5
        assert resp_status == 0
        assert addr_type == 3
        assert host == "mike820324.github.com"
        assert port == 80

        host, port = yield addr_future
        self.server_stream.close()
        assert host == "mike820324.github.com"
        assert port == 80


class TranparentProxyHandlerTest(AsyncTestCase):
    def setUp(self):
        super(TranparentProxyHandlerTest, self).setUp()
        self.handler = TranparentProxyHandler()
        self.asyncSetUp()

    @gen_test
    def asyncSetUp(self):
        listener, port = bind_unused_port()
        event = Event()

        def accept_callback(conn, addr):
            self.server_stream = IOStream(conn)
            self.addCleanup(self.server_stream.close)
            event.set()
        add_accept_handler(listener, accept_callback)
        self.client_stream = IOStream(socket.socket())
        self.addCleanup(self.client_stream.close)
        yield [self.client_stream.connect(('127.0.0.1', port)),
               event.wait()]
        self.io_loop.remove_handler(listener)
        listener.close()

    @gen_test
    def test_read_and_return_addr(self):
        if platform.system() == "Linux":
            addr_future = self.handler.read_and_return_addr(self.server_stream)
            yield self.client_stream.write(struct.pack(
                "!HHBBBBxxxxxxxx",
                0,
                80,
                0x7F,
                0x00,
                0x00,
                0x01))
            self.server_stream.close()

            host, port = yield addr_future
            assert host == "127.0.0.1"
            assert port == 80
        else:
            self.server_stream.close()


class HttpLayerTest(AsyncTestCase):
    def setUp(self):
        super(HttpLayerTest, self).setUp()


def _create_future(result):
    future = Future()
    future.set_result(result)
    return future
