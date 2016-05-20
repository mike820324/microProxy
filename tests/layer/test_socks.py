import socket
import struct

from tornado.testing import AsyncTestCase, gen_test, bind_unused_port
from tornado.locks import Event
from tornado.iostream import IOStream
from tornado.netutil import add_accept_handler, bind_sockets
from tornado.tcpserver import TCPServer

from microproxy.context import Context
from microproxy.layer import SocksLayer


class TestServer(TCPServer):
    def __init__(self):
        super(TestServer, self).__init__()
        self.streams = []
        sockets = bind_sockets(None, 'localhost', socket.AF_INET)
        self.add_sockets(sockets)
        self.port = sockets[0].getsockname()[1]

    def handle_stream(self, stream, address):
        self.stream.append(stream)

    def stop(self):
        super(TestServer, self).stop()
        for stream in self.streams:
            stream.stop()


class SocksProxyHandlerTest(AsyncTestCase):
    def setUp(self):
        super(SocksProxyHandlerTest, self).setUp()
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

        self.context = Context(src_stream=self.server_stream)
        self.layer = SocksLayer(self.context)

    @gen_test
    def test_socks_greeting(self):
        self.layer.socks_greeting()
        yield self.client_stream.write(struct.pack("BBB", 0x05, 0x01, 0x00))
        data = yield self.client_stream.read_bytes(2)
        socks_version, _ = struct.unpack("BB", data)
        self.server_stream.close()
        assert socks_version == 5

    @gen_test
    def test_socks_request_ipv4(self):
        self.server = TestServer()
        addr_future = self.layer.socks_request()
        yield self.client_stream.write(struct.pack("!BBxBIH",
                                                   0x05, 0x01, 0x01,
                                                   0x7F000001, self.server.port))
        data = yield self.client_stream.read_bytes(10)
        socks_version, resp_status, addr_type, host, port = struct.unpack("!BBxBIH", data)
        assert socks_version == 5
        assert resp_status == 0
        assert addr_type == 1
        assert host == 0x7F000001
        assert port == self.server.port

        dest_stream, host, port = yield addr_future
        self.server_stream.close()
        assert isinstance(dest_stream, IOStream)
        assert host == "127.0.0.1"
        assert port == self.server.port
        self.server.stop()

    @gen_test
    def test_socks_request_remote_dns(self):
        self.server = TestServer()
        addr_future = self.layer.socks_request()
        yield self.client_stream.write(struct.pack("!BBxBB{0}sH".format(len("localhost")),
                                                   0x05, 0x01, 0x03,
                                                   len("localhost"), "localhost", self.server.port))
        data = yield self.client_stream.read_bytes(16)
        socks_version, resp_status, addr_type, host, port = struct.unpack("!BBxBx{0}sH".format(len("localhost")), data)
        assert socks_version == 5
        assert resp_status == 0
        assert addr_type == 3
        assert host == "localhost"
        assert port == self.server.port

        dest_stream, host, port = yield addr_future
        self.server_stream.close()
        assert isinstance(dest_stream, IOStream)
        assert host == "localhost"
        assert port == self.server.port
        self.server.stop()
