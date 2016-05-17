import platform
import socket

from tornado.testing import AsyncTestCase, gen_test, bind_unused_port
from tornado.locks import Event
from tornado.iostream import IOStream
from tornado.netutil import add_accept_handler

from microproxy.mode import TransparentProxyHandler


class TranparentProxyHandlerTest(AsyncTestCase):
    def setUp(self):
        super(TranparentProxyHandlerTest, self).setUp()
        self.handler = TransparentProxyHandler()
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

    @gen_test
    def test_read_and_return_addr(self):
        if platform.system() == "Linux":
            addr_future = self.handler.read_and_return_addr(self.server_stream)

            host, port = yield addr_future
            assert host == "127.0.0.1"
            assert port == self.port
        self.server_stream.close()
