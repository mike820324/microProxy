import os
import h11
from tornado.testing import AsyncTestCase, gen_test
from tornado.iostream import PipeIOStream

from microproxy.protocol.http1 import Connection
from microproxy.context import HttpRequest, HttpResponse, HttpHeaders


class ConnectionTest(AsyncTestCase):
    def setUp(self):
        super(ConnectionTest, self).setUp()

        (r, w) = os.pipe()
        self.read_stream = PipeIOStream(r, io_loop=self.io_loop)
        self.write_stream = PipeIOStream(w, io_loop=self.io_loop)
        self.request = None
        self.response = None

    @gen_test
    def test_on_request(self):
        def on_request(request):
            self.request = request

        client_conn = Connection(h11.CLIENT, self.write_stream)
        client_conn.send_request(HttpRequest(
            method="GET", path="/", headers=[("Host", "localhost")]))

        server_conn = Connection(
            h11.SERVER, self.read_stream, on_request=on_request)
        data = yield self.read_stream.read_bytes(
            self.read_stream.max_buffer_size, partial=True)
        server_conn.receive(data)

        self.assertIsNotNone(self.request)
        self.assertEqual(self.request.headers,
                         HttpHeaders([("Host", "localhost")]))
        self.assertEqual(self.request.method, "GET")
        self.assertEqual(self.request.path, "/")
        self.assertEqual(self.request.version, "HTTP/1.1")

    @gen_test
    def test_on_response(self):
        def on_response(response):
            self.response = response

        server_conn = Connection(h11.SERVER, self.write_stream)
        server_conn.send_response(HttpResponse(
            version="HTTP/1.1", code="200", reason="OK",
            headers=[("Host", "localhost"),
                     ("Content-Length", "1")],
            body=b"A"))

        client_conn = Connection(
            h11.CLIENT, self.read_stream, on_response=on_response)
        data = yield self.read_stream.read_bytes(
            self.read_stream.max_buffer_size, partial=True)
        client_conn.receive(data)

        self.assertIsNotNone(self.response)
        self.assertEqual(self.response.headers,
                         HttpHeaders([("Host", "localhost"),
                                      ("Content-Length", "1")]))
        self.assertEqual(self.response.code, "200")
        self.assertEqual(self.response.reason, "OK")
        self.assertEqual(self.response.version, "HTTP/1.1")
        self.assertEqual(self.response.body, b"A")
