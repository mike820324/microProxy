import socket

from tornado.testing import AsyncTestCase, gen_test, bind_unused_port
from tornado.locks import Semaphore
from tornado.iostream import IOStream
from tornado.netutil import add_accept_handler

from microproxy.context import LayerContext
from microproxy.layer import ForwardLayer


class TestForwardLayer(AsyncTestCase):
    def setUp(self):
        super(TestForwardLayer, self).setUp()
        self.asyncSetUp()

    @gen_test
    def asyncSetUp(self):
        listener, port = bind_unused_port()
        semaphore = Semaphore(0)
        server_streams = []

        def accept_callback(conn, addr):
            server_stream = IOStream(conn)
            server_streams.append(server_stream)
            self.addCleanup(server_stream.close)
            semaphore.release()

        add_accept_handler(listener, accept_callback)
        client_streams = [IOStream(socket.socket()), IOStream(socket.socket())]
        for client_stream in client_streams:
            self.addCleanup(client_stream.close)
            yield [client_stream.connect(('127.0.0.1', port)),
                   semaphore.acquire()]
        self.io_loop.remove_handler(listener)
        listener.close()

        self.context = LayerContext(src_stream=server_streams[0],
                                    dest_stream=client_streams[1])
        self.src_stream = client_streams[0]
        self.dest_stream = server_streams[1]
        self.forward_layer = ForwardLayer(self.context)

    @gen_test
    def test_forward_message(self):
        self.forward_layer.process_and_return_context()
        self.src_stream.write(b"aaa\r\n")
        message = yield self.dest_stream.read_until(b"\r\n")
        assert message == b"aaa\r\n"

        self.dest_stream.write(b"bbb\r\n")
        message = yield self.src_stream.read_until(b"\r\n")
        assert message == b"bbb\r\n"

        self.src_stream.close()
        self.dest_stream.close()
        self.context.src_stream.close()
        self.context.dest_stream.close()
