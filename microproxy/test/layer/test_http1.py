import socket
from mock import Mock

from tornado.testing import AsyncTestCase, gen_test, bind_unused_port
from tornado.locks import Semaphore
from tornado.iostream import IOStream
from tornado.netutil import add_accept_handler

from microproxy.context import LayerContext
from microproxy.config import Config
from microproxy.layer import Http1Layer
from microproxy.exception import SrcStreamClosedError, DestStreamClosedError


class TestHttp1Layer(AsyncTestCase):
    def setUp(self):
        super(TestHttp1Layer, self).setUp()
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
                                    dest_stream=client_streams[1],
                                    config=Config(dict(mode="socks")))

        self.interceptor = Mock()
        self.interceptor.publish = Mock(return_value=None)
        self.interceptor.request = Mock(return_value=None)
        self.interceptor.response = Mock(return_value=None)
        self.context.interceptor = self.interceptor

        self.src_stream = client_streams[0]
        self.dest_stream = server_streams[1]
        self.http_layer = Http1Layer(self.context)

    @gen_test
    def test_process_and_return_context_normal(self):
        http_layer_future = self.http_layer.process_and_return_context()
        self.src_stream.write(b"\r\n".join([b"GET /index HTTP/1.1",
                                            b"Host: localhost",
                                            b"\r\n"]))

        req_header = yield self.dest_stream.read_until("\r\n\r\n")
        self.assertEqual(
            req_header,
            b"\r\n".join([b"GET /index HTTP/1.1",
                          b"Host: localhost",
                          b"\r\n"]))
        yield self.dest_stream.write(b"\r\n".join([b"HTTP/1.1 200 OK",
                                                   b"Transfer-Encoding: chunked\r\n",
                                                   b"4",
                                                   b"Body",
                                                   b"0",
                                                   b"\r\n"]))

        resp = yield self.src_stream.read_until(b"0\r\n\r\n")
        self.assertEqual(
            resp,
            b"\r\n".join([b"HTTP/1.1 200 OK",
                          b"transfer-encoding: chunked\r\n",
                          b"4",
                          b"Body",
                          b"0",
                          b"\r\n"]))

        self.src_stream.close()
        self.dest_stream.close()
        self.context.src_stream.close()
        self.context.dest_stream.close()
        yield http_layer_future

    @gen_test
    def test_write_req_to_dest_failed(self):
        http_layer_future = self.http_layer.process_and_return_context()
        self.dest_stream.close()
        yield self.src_stream.write(b"\r\n".join([b"GET /index HTTP/1.1",
                                                  b"Host: localhost",
                                                  b"\r\n"]))

        with self.assertRaises(DestStreamClosedError):
            yield http_layer_future

    @gen_test
    def test_read_resp_from_dest_failed(self):
        http_layer_future = self.http_layer.process_and_return_context()
        self.dest_stream.close()
        yield self.src_stream.write(b"\r\n".join([b"GET /index HTTP/1.1",
                                                  b"Host: localhost",
                                                  b"\r\n"]))
        with self.assertRaises(DestStreamClosedError):
            yield http_layer_future

    @gen_test
    def test_write_resp_to_src_failed(self):
        http_layer_future = self.http_layer.process_and_return_context()
        self.src_stream.write(b"\r\n".join([b"GET /index HTTP/1.1",
                                            b"Host: localhost",
                                            b"\r\n"]))
        self.src_stream.close()
        yield self.dest_stream.read_until("\r\n\r\n")
        yield self.dest_stream.write(b"\r\n".join([b"HTTP/1.1 200 OK",
                                                   b"Transfer-Encoding: chunked\r\n",
                                                   b"4",
                                                   b"Body",
                                                   b"0",
                                                   b"\r\n"]))
        with self.assertRaises(SrcStreamClosedError):
            yield http_layer_future

        self.dest_stream.close()
        self.context.src_stream.close()
        self.context.dest_stream.close()

    @gen_test
    def test_replay(self):
        self.context.config = Config(dict(mode="replay"))

        http_layer_future = self.http_layer.process_and_return_context()
        self.src_stream.write(b"\r\n".join([b"GET /index HTTP/1.1",
                                            b"Host: localhost",
                                            b"\r\n"]))
        yield self.dest_stream.read_until("\r\n\r\n")
        yield self.dest_stream.write(b"\r\n".join([b"HTTP/1.1 200 OK",
                                                   b"Transfer-Encoding: chunked\r\n",
                                                   b"4",
                                                   b"Body",
                                                   b"0",
                                                   b"\r\n"]))
        yield self.src_stream.read_until(b"0\r\n\r\n")

        yield http_layer_future
        self.assertTrue(self.context.src_stream.closed())
        self.assertTrue(self.context.dest_stream.closed())

    @gen_test
    def test_on_websocket(self):
        http_layer_future = self.http_layer.process_and_return_context()
        self.src_stream.write(b"\r\n".join([b"GET /chat HTTP/1.1",
                                            b"Host: localhost",
                                            b"Upgrade: websocket",
                                            b"\r\n"]))

        yield self.dest_stream.read_until("\r\n\r\n")
        yield self.dest_stream.write(b"\r\n".join([b"HTTP/1.1 101 Switch Protocols",
                                                   b"Upgrade: websocket",
                                                   b"Connection: Upgrade",
                                                   b"\r\n"]))

        yield http_layer_future
        self.assertFalse(self.context.src_stream.closed())
        self.assertFalse(self.context.dest_stream.closed())

    def tearDown(self):
        self.src_stream.close()
        self.dest_stream.close()
        self.context.src_stream.close()
        self.context.dest_stream.close()
