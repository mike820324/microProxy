import socket
from mock import Mock

from tornado.testing import AsyncTestCase, gen_test, bind_unused_port
from tornado.locks import Semaphore
from tornado.iostream import IOStream
from tornado.netutil import add_accept_handler

from microproxy.context import LayerContext
from microproxy.config import Config
from microproxy.layer import Http2Layer
from microproxy.protocol.http2 import Connection
from microproxy.context import HttpRequest, HttpResponse, HttpHeaders


class TestHttp2Layer(AsyncTestCase):
    def setUp(self):
        super(TestHttp2Layer, self).setUp()
        self.asyncSetUp()
        self.src_events = []
        self.dest_events = []

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

        self.http_layer = Http2Layer(self.context)

    def record_src_event(self, *args):
        self.src_events.append(args)

    def record_dest_event(self, *args):
        self.dest_events.append(args)

    def ignore_event(self, *args):
        pass

    @gen_test
    def test_req_and_resp(self):
        self.client_conn = Connection(
            self.src_stream, client_side=True,
            on_response=self.record_src_event,
            on_unhandled=self.ignore_event)
        self.server_conn = Connection(
            self.dest_stream, client_side=False,
            on_request=self.record_dest_event,
            on_unhandled=self.ignore_event)

        result_future = self.http_layer.process_and_return_context()
        self.client_conn.initiate_connection()
        self.server_conn.initiate_connection()

        yield self.client_conn.read_bytes()
        yield self.server_conn.read_bytes()

        self.client_conn.send_request(
            1, HttpRequest(headers=[
                (":method", "GET"),
                (":path", "/"),
                ("aaa", "bbb")]))

        yield self.server_conn.read_bytes()

        self.server_conn.send_response(
            1, HttpResponse(headers=[(":status", "200"), ("aaa", "bbb")],
                            body=b"ccc"))

        yield self.client_conn.read_bytes()
        yield self.client_conn.read_bytes()

        print self.src_events
        print self.dest_events

        self.src_stream.close()
        self.dest_stream.close()

        result = yield result_future
        self.assertIsNotNone(result)
        self.assertIsInstance(result, LayerContext)

        self.assertEqual(len(self.src_events), 1)
        stream_id, response = self.src_events[0]
        self.assertEqual(stream_id, 1)
        self.assertEqual(response.code, "200")
        self.assertEqual(response.version, "HTTP/2")
        self.assertEqual(
            response.headers,
            HttpHeaders([(":status", "200"),
                         ("aaa", "bbb")]))

        self.assertEqual(len(self.dest_events), 1)
        stream_id, request, _ = self.dest_events[0]
        self.assertEqual(stream_id, 1)
        self.assertEqual(request.method, "GET")
        self.assertEqual(request.path, "/")
        self.assertEqual(request.version, "HTTP/2")
        self.assertEqual(
            request.headers,
            HttpHeaders([(":method", "GET"),
                         (":path", "/"),
                         ("aaa", "bbb")]))

    def tearDown(self):
        self.src_stream.close()
        self.dest_stream.close()
        self.context.src_stream.close()
        self.context.dest_stream.close()
