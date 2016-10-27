import h11
import mock
from tornado.testing import gen_test

from microproxy.test.utils import ProxyAsyncTestCase
from microproxy.protocol.http1 import Connection
from microproxy.context import HttpRequest, HttpResponse, HttpHeaders


class TestConnection(ProxyAsyncTestCase):
    def setUp(self):
        super(TestConnection, self).setUp()
        self.asyncSetUp()
        self.request = None
        self.response = None

    def on_request(self, request):
        self.request = request

    def on_response(self, response):
        self.response = response

    @gen_test
    def asyncSetUp(self):
        self.client_stream, self.server_stream = yield self.create_iostream_pair()
        self.addCleanup(self.client_stream.close)
        self.addCleanup(self.server_stream.close)

    @gen_test
    def test_on_request(self):
        client_conn = Connection(h11.CLIENT, self.client_stream)
        client_conn.send_request(HttpRequest(
            method="GET", path="/", headers=[("Host", "localhost")]))

        server_conn = Connection(
            h11.SERVER, self.server_stream, on_request=self.on_request)
        yield server_conn.read_bytes()

        self.assertIsNotNone(self.request)
        self.assertEqual(self.request.headers,
                         HttpHeaders([("host", "localhost")]))
        self.assertEqual(self.request.method, "GET")
        self.assertEqual(self.request.path, "/")
        self.assertEqual(self.request.version, "HTTP/1.1")

    @gen_test
    def test_on_response(self):
        server_conn = Connection(h11.SERVER, self.server_stream)
        server_conn.send_response(HttpResponse(
            version="HTTP/1.1", code="200", reason="OK",
            headers=[("Host", "localhost"),
                     ("Content-Length", "1")],
            body=b"A"))

        client_conn = Connection(
            h11.CLIENT, self.client_stream, on_response=self.on_response)
        yield client_conn.read_bytes()

        self.assertIsNotNone(self.response)
        self.assertEqual(self.response.headers,
                         HttpHeaders([("host", "localhost"),
                                      ("content-length", "1")]))
        self.assertEqual(self.response.code, "200")
        self.assertEqual(self.response.reason, "OK")
        self.assertEqual(self.response.version, "HTTP/1.1")
        self.assertEqual(self.response.body, b"A")

    @gen_test
    def test_on_info_response(self):
        client_conn = Connection(
            h11.CLIENT, self.client_stream, on_info_response=self.on_response)
        client_conn.send_request(HttpRequest(
            method="GET", path="/chat", version="HTTP/1.1",
            headers=[("Host", "localhost"), ("Upgrade", "websocket")]))

        server_conn = Connection(h11.SERVER, self.server_stream, on_request=self.on_request)
        yield server_conn.read_bytes()
        server_conn.send_info_response(HttpResponse(
            version="HTTP/1.1", code="101", reason="Protocol Upgrade",
            headers=[("Host", "localhost"),
                     ("Upgrade", "websocket")]))

        yield client_conn.read_bytes()

        self.assertIsNotNone(self.response)
        self.assertEqual(self.response.headers,
                         HttpHeaders([("host", "localhost"),
                                      ("upgrade", "websocket")]))
        self.assertEqual(self.response.code, "101")
        self.assertEqual(self.response.reason, "Protocol Upgrade")
        self.assertEqual(self.response.version, "HTTP/1.1")

    @gen_test
    def test_on_post_request(self):
        client_conn = Connection(h11.CLIENT, self.client_stream)
        client_conn.send_request(HttpRequest(
            method="POST", path="/",
            headers=[("Host", "localhost"), ("Content-Length", "4")],
            body=b"yaya"))

        server_conn = Connection(
            h11.SERVER, self.server_stream, on_request=self.on_request)
        yield server_conn.read_bytes()

        self.assertIsNotNone(self.request)
        self.assertEqual(self.request.headers,
                         HttpHeaders([("host", "localhost"), ("content-length", "4")]))
        self.assertEqual(self.request.method, "POST")
        self.assertEqual(self.request.path, "/")
        self.assertEqual(self.request.version, "HTTP/1.1")
        self.assertEqual(self.request.body, b"yaya")

    @gen_test
    def test_on_connection_closed(self):
        client_conn = Connection(
            h11.CLIENT, self.client_stream, on_response=self.on_response)
        client_conn.send_request(HttpRequest(
            method="GET", path="/",
            headers=[("Host", "localhost"), ("Connection", "close")]))

        server_conn = Connection(
            h11.SERVER, self.server_stream, on_request=self.on_request)
        yield server_conn.read_bytes()
        server_conn.send_response(HttpResponse(
            version="HTTP/1.1", code="200", reason="OK",
            headers=[("Host", "localhost"),
                     ("Content-Length", "4")],
            body=b"Yaya"))

        yield client_conn.read_bytes()
        self.assertTrue(self.client_stream.closed())
        self.assertTrue(self.server_stream.closed())

    def test_parse_version(self):
        self.assertEqual(
            Connection(h11.CLIENT, None)._parse_version(None),
            "HTTP/1.1")

        http_content = mock.Mock()
        http_content.http_version = "1.1"
        self.assertEqual(
            Connection(h11.CLIENT, None)._parse_version(http_content),
            "HTTP/1.1")

    def tearDown(self):
        self.client_stream.close()
        self.server_stream.close()
