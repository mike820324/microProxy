import socket
import mock
from tornado.testing import AsyncTestCase, gen_test, bind_unused_port
from tornado.locks import Event
from tornado.iostream import IOStream
from tornado.netutil import add_accept_handler

from microproxy.protocol.http2 import Connection
from microproxy.context import HttpRequest, HttpResponse, HttpHeaders


class ConnectionTest(AsyncTestCase):
    def setUp(self):
        super(ConnectionTest, self).setUp()
        self.asyncSetUp()
        self.request = None
        self.response = None
        self.settings = None

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

    def on_request(self, stream_id, request, priority_updated):
        self.request = request

    def on_response(self, stream_id, response):
        self.response = response

    def on_settings(self, settings):
        self.settings = settings

    @gen_test
    def test_on_request(self):
        client_conn = Connection(self.client_stream, client_side=True)
        client_conn.initiate_connection()
        client_conn.send_request(
            client_conn.get_next_available_stream_id(),
            HttpRequest(headers=[
                (":method", "GET"),
                (":path", "/"),
                ("aaa", "bbb")]))

        server_conn = Connection(
            self.server_stream, client_side=False, on_request=self.on_request,
            on_settings=self.on_settings)
        server_conn.initiate_connection()
        data = yield self.server_stream.read_bytes(
            self.server_stream.max_buffer_size, partial=True)
        server_conn.receive(data)

        self.assertIsNotNone(self.request)
        self.assertEqual(self.request.headers,
                         HttpHeaders([
                             (":method", "GET"),
                             (":path", "/"),
                             ("aaa", "bbb")]))
        self.assertEqual(self.request.method, "GET")
        self.assertEqual(self.request.path, "/")
        self.assertEqual(self.request.version, "HTTP/2")
        self.client_stream.close()
        self.server_stream.close()

    @gen_test
    def test_on_response(self):
        client_conn = Connection(
            self.client_stream, client_side=True, on_response=self.on_response,
            on_settings=mock.Mock())
        client_conn.initiate_connection()
        stream_id = client_conn.get_next_available_stream_id()
        client_conn.send_request(
            stream_id,
            HttpRequest(headers=[
                (":method", "GET"),
                (":path", "/"),
                ("aaa", "bbb")]))

        server_conn = Connection(
            self.server_stream, client_side=False,
            on_request=mock.Mock(), on_settings=mock.Mock())
        server_conn.initiate_connection()
        data = yield self.server_stream.read_bytes(
            self.server_stream.max_buffer_size, partial=True)
        server_conn.receive(data)
        server_conn.send_response(
            stream_id,
            HttpResponse(
                headers=[(":status", "200"),
                         ("aaa", "bbb")],
                body=b"ccc"))

        data = yield self.client_stream.read_bytes(
            self.client_stream.max_buffer_size, partial=True)
        client_conn.receive(data)

        self.assertIsNotNone(self.response)
        self.assertEqual(self.response.headers,
                         HttpHeaders([
                             (":status", "200"),
                             ("aaa", "bbb")]))
        self.assertEqual(self.response.code, "200")
        self.assertEqual(self.response.version, "HTTP/2")
        self.client_stream.close()
        self.server_stream.close()
