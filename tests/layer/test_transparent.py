import platform
import socket

from tornado.testing import AsyncTestCase, gen_test, bind_unused_port
from tornado.locks import Event
from tornado.iostream import IOStream
from tornado.netutil import add_accept_handler, bind_sockets
from tornado.tcpserver import TCPServer

from microproxy.layer import TransparentLayer
from microproxy.context import Context


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

class TranparentProxyHandlerTest(AsyncTestCase):
    def setUp(self):
        super(TranparentProxyHandlerTest, self).setUp()
        self.asyncSetUp()

    @gen_test
    def asyncSetUp(self):
        listener, port = bind_unused_port()
        self.port = port
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
        self.layer = TransparentLayer(self.context)

    @gen_test
    def test_read_and_return_addr(self):
        self.server = TCPServer()
        if platform.system() == "Linux":
            addr_future = self.layer._get_dest_addr(self.src_stream)

            dest_stream, host, port = yield addr_future
            assert isinstance(dest_stream, IOStream)
            assert host == "127.0.0.1"
            assert port == self.port
        self.server.stop()
        self.server_stream.close()
