import socket
import struct

from tornado.testing import AsyncTestCase, gen_test, bind_unused_port
from tornado.locks import Event
from tornado.iostream import IOStream
from tornado.netutil import add_accept_handler

from microproxy.context import Context
from microproxy.layer import SocksLayer


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

        dest_listener, dest_port = bind_unused_port()
        self.listener = dest_listener
        self.port = dest_port

        def dest_accept_callback(conn, addr):
            self.dest_server_stream = IOStream(conn)
            self.addCleanup(self.dest_server_stream.close)
        add_accept_handler(dest_listener, dest_accept_callback)
        self.addCleanup(dest_listener.close)

    @gen_test
    def test_socks_greeting(self):
        greeting = self.layer.socks_greeting()
        yield self.client_stream.write(struct.pack("BBB", 0x05, 0x01, 0x00))
        yield greeting
        data = yield self.client_stream.read_bytes(2)
        socks_version, _ = struct.unpack("BB", data)
        self.client_stream.close()
        self.server_stream.close()
        assert socks_version == 5

    @gen_test
    def test_socks_request_ipv4(self):
        addr_future = self.layer.socks_request()
        yield self.client_stream.write(struct.pack("!BBxBIH",
                                                   0x05, 0x01, 0x01,
                                                   0x7F000001, 80))

        host, port, addr_type = yield addr_future
        self.client_stream.close()
        self.server_stream.close()
        assert host == "127.0.0.1"
        assert port == 80
        assert addr_type == 0x01

    @gen_test
    def test_socks_request_remote_dns(self):
        addr_future = self.layer.socks_request()
        yield self.client_stream.write(struct.pack("!BBxBB{0}sH".format(len("localhost")),
                                                   0x05, 0x01, 0x03,
                                                   len("localhost"), "localhost", 80))

        host, port, addr_type = yield addr_future
        self.client_stream.close()
        self.server_stream.close()
        assert host == "localhost"
        assert port == 80
        assert addr_type == 0x03

    @gen_test
    def test_socks_response_ipv4(self):
        dest_stream = yield self.layer.socks_response_with_dest_stream_creation(u"127.0.0.1", self.port, 0x01)
        socks_response_content = yield self.client_stream.read_bytes(10)

        version, status, addr_type, host, port = struct.unpack("!BBxBIH", socks_response_content)

        assert version == 5
        assert status == 0
        assert addr_type == 1
        assert host == 0x7F000001
        assert port == self.port

        dest_stream.close()
        self.dest_server_stream.close()
        self.client_stream.close()
        self.server_stream.close()

    @gen_test
    def test_socks_response_domain(self):
        dest_stream = yield self.layer.socks_response_with_dest_stream_creation("localhost", self.port, 0x03)
        socks_response_content = yield self.client_stream.read_bytes(16)

        version, status, addr_type, host, port = struct.unpack("!BBxBx9sH", socks_response_content)

        assert version == 5
        assert status == 0
        assert addr_type == 3
        assert host == "localhost"
        assert port == self.port

        dest_stream.close()
        self.dest_server_stream.close()
        self.client_stream.close()
        self.server_stream.close()
