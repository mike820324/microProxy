import h11
import mock
from tornado.gen import coroutine, sleep
from tornado.netutil import add_accept_handler
from tornado.testing import gen_test, bind_unused_port
from unittest import TestCase

from microproxy.context import (
    HttpRequest, HttpResponse, HttpHeaders,
    LayerContext, ServerContext
)
from microproxy.exception import SrcStreamClosedError, DestStreamClosedError
from microproxy.layer import Http1Layer
from microproxy.layer.application.http1 import (
    parse_proxy_path, parse_tunnel_proxy_path)
from microproxy.protocol.http1 import Connection
from microproxy.tornado_ext.iostream import MicroProxyIOStream
from microproxy.test.utils import ProxyAsyncTestCase


class TestHtt1(TestCase):
    def test_parse_proxy_path_http_80(self):
        self.assertEqual(
            parse_proxy_path("http://example.com/"),
            ("http", "example.com", 80, "/"))

    def test_parse_proxy_path_http_8080(self):
        self.assertEqual(
            parse_proxy_path("http://example.com:8080/"),
            ("http", "example.com", 8080, "/"))

    def test_parse_proxy_path_https_443(self):
        self.assertEqual(
            parse_proxy_path("https://example.com/"),
            ("https", "example.com", 443, "/"))

    def test_parse_proxy_path_https_8443(self):
        self.assertEqual(
            parse_proxy_path("https://example.com:8443/"),
            ("https", "example.com", 8443, "/"))

    def test_parse_proxy_path_http_80_index(self):
        self.assertEqual(
            parse_proxy_path("http://example.com/index"),
            ("http", "example.com", 80, "/index"))

    def test_parse_proxy_path_without_scheme(self):
        with self.assertRaises(ValueError):
            parse_proxy_path("example.com/")

    def test_parse_proxy_path_without_path(self):
        with self.assertRaises(ValueError):
            parse_proxy_path("http://example.com")

    def test_parse_tunnel_proxy_path_http_80(self):
        self.assertEqual(
            parse_tunnel_proxy_path("example.com:80"),
            ("http", "example.com", 80))

    def test_parse_tunnel_proxy_path_https_443(self):
        self.assertEqual(
            parse_tunnel_proxy_path("example.com:443"),
            ("https", "example.com", 443))

    def test_parse_tunnel_proxy_path_without_port(self):
        with self.assertRaises(ValueError):
            parse_tunnel_proxy_path("example.com")


class TestHttp1Layer(ProxyAsyncTestCase):
    def setUp(self):
        super(TestHttp1Layer, self).setUp()
        self.asyncSetUp()
        self.src_events = []
        self.dest_events = []

    @gen_test
    def asyncSetUp(self):
        self.client_stream, src_stream = yield self.create_iostream_pair()
        dest_stream, self.server_stream = yield self.create_iostream_pair()

        server_state = ServerContext(
            config={},
            interceptor=mock.Mock(**{
                "publish.return_value": None,
                "request.return_value": None,
                "response.return_value": None,
            })
        )

        self.http_layer = Http1Layer(
            server_state,
            LayerContext(mode="socks",
                         src_stream=src_stream, dest_stream=dest_stream))

        self.client_conn = Connection(
            h11.CLIENT, self.client_stream,
            on_response=self.record_src_event,
            on_info_response=self.record_src_event,
            on_unhandled=self.ignore_event)

        self.server_conn = Connection(
            h11.SERVER, self.server_stream,
            on_request=self.record_dest_event,
            on_unhandled=self.ignore_event)

    def record_src_event(self, *args):
        self.src_events.append(args)

    def record_dest_event(self, *args):
        self.dest_events.append(args)

    def ignore_event(self, *args):
        pass

    @coroutine
    def read_until_new_event(self, conn, events):
        while len(events) == 0:
            yield conn.read_bytes()

    @gen_test
    def test_req_and_resp(self):
        http_layer_future = self.http_layer.process_and_return_context()
        self.client_conn.send_request(HttpRequest(
            version="HTTP/1.1", method="GET", path="/index",
            headers=[("Host", "localhost")]))

        yield self.read_until_new_event(self.server_conn, self.dest_events)
        self.assertEqual(len(self.dest_events), 1)
        request, = self.dest_events[0]
        self.assertIsInstance(request, HttpRequest)
        self.assertEqual(request.method, "GET")
        self.assertEqual(request.version, "HTTP/1.1")
        self.assertEqual(request.path, "/index")
        self.assertEqual(request.headers, HttpHeaders([("host", "localhost")]))

        self.server_conn.send_response(HttpResponse(
            version="HTTP/1.1", code="200", reason="OK",
            headers=[("Content-Type", "plain/text")], body="body"))

        yield self.read_until_new_event(self.client_conn, self.src_events)
        self.assertEqual(len(self.src_events), 1)
        response, = self.src_events[0]
        self.assertIsInstance(response, HttpResponse)
        self.assertEqual(response.code, "200")
        self.assertEqual(response.version, "HTTP/1.1")
        self.assertEqual(response.reason, "OK")
        self.assertEqual(
            response.headers,
            HttpHeaders([("content-type", "plain/text"), ("transfer-encoding", "chunked")]))
        self.assertEqual(response.body, "body")

        self.assertTrue(http_layer_future.running())

        self.client_stream.close()
        self.server_stream.close()
        self.http_layer.src_stream.close()
        self.http_layer.dest_stream.close()
        yield http_layer_future

    @gen_test
    def test_write_req_to_dest_failed(self):
        http_layer_future = self.http_layer.process_and_return_context()
        self.server_stream.close()
        self.client_conn.send_request(HttpRequest(
            version="HTTP/1.1", method="GET", path="/index",
            headers=[("Host", "localhost")]))

        with self.assertRaises(DestStreamClosedError):
            yield http_layer_future

    @gen_test
    def test_read_resp_from_dest_failed(self):
        http_layer_future = self.http_layer.process_and_return_context()
        self.client_conn.send_request(HttpRequest(
            version="HTTP/1.1", method="GET", path="/index",
            headers=[("Host", "localhost")]))

        self.assertTrue(http_layer_future.running())
        self.server_stream.close()

        with self.assertRaises(DestStreamClosedError):
            yield http_layer_future

    @gen_test
    def test_write_resp_to_src_failed(self):
        http_layer_future = self.http_layer.process_and_return_context()

        self.client_conn.send_request(HttpRequest(
            version="HTTP/1.1", method="GET", path="/index",
            headers=[("Host", "localhost")]))

        yield self.read_until_new_event(self.server_conn, self.dest_events)
        self.assertEqual(len(self.dest_events), 1)
        request, = self.dest_events.pop()
        self.assertIsInstance(request, HttpRequest)
        self.assertEqual(request.method, "GET")
        self.assertEqual(request.version, "HTTP/1.1")
        self.assertEqual(request.path, "/index")
        self.assertEqual(request.headers, HttpHeaders([("host", "localhost")]))

        self.client_stream.close()

        self.server_conn.send_response(HttpResponse(
            version="HTTP/1.1", code="200", reason="OK",
            headers=[("Content-Type", "plain/text")]))

        with self.assertRaises(SrcStreamClosedError):
            yield http_layer_future

    @gen_test
    def test_replay(self):
        self.http_layer.context.mode = "replay"

        http_layer_future = self.http_layer.process_and_return_context()
        self.client_conn.send_request(HttpRequest(
            version="HTTP/1.1", method="GET", path="/index",
            headers=[("Host", "localhost")]))

        yield self.read_until_new_event(self.server_conn, self.dest_events)
        self.assertEqual(len(self.dest_events), 1)
        request, = self.dest_events.pop()
        self.assertIsInstance(request, HttpRequest)
        self.assertEqual(request.method, "GET")
        self.assertEqual(request.version, "HTTP/1.1")
        self.assertEqual(request.path, "/index")
        self.assertEqual(request.headers, HttpHeaders([("host", "localhost")]))

        self.server_conn.send_response(HttpResponse(
            version="HTTP/1.1", code="200", reason="OK",
            headers=[("Content-Type", "plain/text")], body="body"))

        yield self.read_until_new_event(self.client_conn, self.src_events)
        self.assertEqual(len(self.src_events), 1)
        response, = self.src_events.pop()
        self.assertIsInstance(response, HttpResponse)
        self.assertEqual(response.code, "200")
        self.assertEqual(response.version, "HTTP/1.1")
        self.assertEqual(response.reason, "OK")
        self.assertEqual(
            response.headers,
            HttpHeaders([("content-type", "plain/text"), ("transfer-encoding", "chunked")]))
        self.assertEqual(response.body, "body")

        self.assertTrue(http_layer_future.done())

        yield http_layer_future
        self.assertTrue(self.http_layer.src_stream.closed())
        self.assertTrue(self.http_layer.dest_stream.closed())

    @gen_test
    def test_on_websocket(self):
        http_layer_future = self.http_layer.process_and_return_context()

        self.client_conn.send_request(HttpRequest(
            version="HTTP/1.1", method="GET", path="/chat",
            headers=[("Host", "localhost"), ("Upgrade", "websocket")]))

        yield self.read_until_new_event(self.server_conn, self.dest_events)
        self.assertEqual(len(self.dest_events), 1)
        request, = self.dest_events.pop()
        self.assertIsInstance(request, HttpRequest)
        self.assertEqual(request.method, "GET")
        self.assertEqual(request.version, "HTTP/1.1")
        self.assertEqual(request.path, "/chat")
        self.assertEqual(request.headers,
                         HttpHeaders([("host", "localhost"),
                                      ("upgrade", "websocket")]))

        self.server_conn.send_info_response(HttpResponse(
            version="HTTP/1.1", code="101", reason="Switching Protocol",
            headers=[("Upgrade", "websocket"), ("Connection", "Upgrade")]))

        yield self.read_until_new_event(self.client_conn, self.src_events)
        self.assertEqual(len(self.src_events), 1)
        response, = self.src_events.pop()
        self.assertIsInstance(response, HttpResponse)
        self.assertEqual(response.code, "101")
        self.assertEqual(response.version, "HTTP/1.1")
        self.assertEqual(response.reason, "Switching Protocol")
        self.assertEqual(
            response.headers,
            HttpHeaders([("upgrade", "websocket"), ("connection", "Upgrade")]))

        self.assertTrue(http_layer_future.done())
        yield http_layer_future
        self.assertFalse(self.http_layer.src_stream.closed())
        self.assertFalse(self.http_layer.dest_stream.closed())

    @gen_test
    def test_read_response_without_chunked_and_content_length(self):
        http_layer_future = self.http_layer.process_and_return_context()
        self.client_conn.send_request(HttpRequest(
            version="HTTP/1.1", method="GET", path="/index",
            headers=[("Host", "localhost")]))

        yield self.read_until_new_event(self.server_conn, self.dest_events)
        self.assertEqual(len(self.dest_events), 1)
        request, = self.dest_events.pop()
        self.assertIsInstance(request, HttpRequest)
        self.assertEqual(request.method, "GET")
        self.assertEqual(request.version, "HTTP/1.1")
        self.assertEqual(request.path, "/index")
        self.assertEqual(request.headers, HttpHeaders([("host", "localhost")]))

        yield self.server_stream.write(
            (b"HTTP/1.1 200 OK\r\n"
             b"Connection: closed\r\n\r\n"
             b"body"))

        self.server_stream.close()

        yield self.read_until_new_event(self.client_conn, self.src_events)
        self.assertEqual(len(self.src_events), 1)
        response, = self.src_events.pop()
        self.assertIsInstance(response, HttpResponse)
        self.assertEqual(response.code, "200")
        self.assertEqual(response.version, "HTTP/1.1")
        self.assertEqual(response.reason, "OK")
        self.assertEqual(
            response.headers,
            HttpHeaders([("connection", "closed"), ('transfer-encoding', 'chunked')]))
        self.assertEqual(response.body, "body")

        self.assertTrue(http_layer_future.done())

        yield http_layer_future

    @gen_test
    def test_write_info_resp_to_src_failed(self):
        http_layer_future = self.http_layer.process_and_return_context()

        self.client_conn.send_request(HttpRequest(
            version="HTTP/1.1", method="GET", path="/chat",
            headers=[("Host", "localhost"), ("Upgrade", "websocket")]))

        yield self.read_until_new_event(self.server_conn, self.dest_events)
        self.assertEqual(len(self.dest_events), 1)
        request, = self.dest_events.pop()
        self.assertIsInstance(request, HttpRequest)
        self.assertEqual(request.method, "GET")
        self.assertEqual(request.version, "HTTP/1.1")
        self.assertEqual(request.path, "/chat")
        self.assertEqual(request.headers, HttpHeaders([("host", "localhost"), ("upgrade", "websocket")]))

        self.client_stream.close()

        self.server_conn.send_info_response(HttpResponse(
            version="HTTP/1.1", code="101", reason="Switching Protocol",
            headers=[("Content-Type", "plain/text")]))

        with self.assertRaises(SrcStreamClosedError):
            yield http_layer_future

    def tearDown(self):
        self.client_stream.close()
        self.server_stream.close()
        self.http_layer.src_stream.close()
        self.http_layer.dest_stream.close()


class TestHttp1LayerProxying(ProxyAsyncTestCase):
    def setUp(self):
        super(TestHttp1LayerProxying, self).setUp()
        self.asyncSetUp()
        self.src_events = []
        self.dest_events = []

    @gen_test
    def asyncSetUp(self):
        self.client_stream, src_stream = yield self.create_iostream_pair()

        self.listener, self.port = bind_unused_port()
        add_accept_handler(self.listener, self.on_server_connnect)

        server_state = ServerContext(
            config={},
            interceptor=mock.Mock(**{
                "publish.return_value": None,
                "request.return_value": None,
                "response.return_value": None,
            })
        )

        self.http_layer = Http1Layer(
            server_state,
            LayerContext(
                mode="http",
                src_stream=src_stream))

        self.client_conn = Connection(
            h11.CLIENT, self.client_stream,
            on_response=self.record_src_event,
            on_info_response=self.record_src_event,
            on_unhandled=self.ignore_event)

        self.server_stream = None
        self.server_conn = None

    def on_server_connnect(self, conn, addr):
        self.server_stream = MicroProxyIOStream(conn)
        self.server_conn = Connection(
            h11.SERVER, self.server_stream,
            on_request=self.record_dest_event,
            on_unhandled=self.ignore_event)

    def record_src_event(self, *args):
        self.src_events.append(args)

    def record_dest_event(self, *args):
        self.dest_events.append(args)

    def ignore_event(self, *args):
        pass

    @coroutine
    def read_until_new_event(self, conn, events):
        while len(events) == 0:
            yield conn.read_bytes()

    @coroutine
    def wait_for_server_connect(self):
        while not self.server_stream:
            yield sleep(0.1)

    @gen_test
    def test_proxy(self):
        http_layer_future = self.http_layer.process_and_return_context()
        path = "http://127.0.0.1:{0}/".format(self.port)
        self.client_conn.send_request(HttpRequest(
            version="HTTP/1.1", method="GET", path=path,
            headers=[("Host", "localhost")]))

        yield self.wait_for_server_connect()
        yield self.read_until_new_event(self.server_conn, self.dest_events)
        self.assertEqual(len(self.dest_events), 1)
        request, = self.dest_events[0]
        self.assertIsInstance(request, HttpRequest)
        self.assertEqual(request.method, "GET")
        self.assertEqual(request.version, "HTTP/1.1")
        self.assertEqual(request.path, "/")
        self.assertEqual(request.headers, HttpHeaders([("host", "localhost")]))

        self.server_conn.send_response(HttpResponse(
            version="HTTP/1.1", code="200", reason="OK",
            headers=[("Content-Type", "plain/text")], body="body"))

        yield self.read_until_new_event(self.client_conn, self.src_events)
        self.assertEqual(len(self.src_events), 1)
        response, = self.src_events[0]
        self.assertIsInstance(response, HttpResponse)
        self.assertEqual(response.code, "200")
        self.assertEqual(response.version, "HTTP/1.1")
        self.assertEqual(response.reason, "OK")
        self.assertEqual(
            response.headers,
            HttpHeaders([("content-type", "plain/text"), ("transfer-encoding", "chunked")]))
        self.assertEqual(response.body, "body")

        self.assertTrue(http_layer_future.running())

        self.client_stream.close()
        self.server_stream.close()
        self.http_layer.src_stream.close()
        self.http_layer.dest_stream.close()
        yield http_layer_future

    @gen_test
    def test_proxy_reuse_connection(self):
        http_layer_future = self.http_layer.process_and_return_context()
        path = "http://127.0.0.1:{0}/".format(self.port)
        self.client_conn.send_request(HttpRequest(
            version="HTTP/1.1", method="GET", path=path,
            headers=[("Host", "localhost")]))

        yield self.wait_for_server_connect()
        yield self.read_until_new_event(self.server_conn, self.dest_events)
        self.assertEqual(len(self.dest_events), 1)
        request, = self.dest_events.pop()
        self.assertIsInstance(request, HttpRequest)

        self.server_conn.send_response(HttpResponse(
            version="HTTP/1.1", code="200", reason="OK",
            headers=[("Content-Type", "plain/text")], body="body"))

        yield self.read_until_new_event(self.client_conn, self.src_events)
        self.assertEqual(len(self.src_events), 1)
        response, = self.src_events.pop()
        self.assertIsInstance(response, HttpResponse)

        self.assertTrue(http_layer_future.running())

        self.client_conn.start_next_cycle()
        self.server_conn.start_next_cycle()

        self.client_conn.send_request(HttpRequest(
            version="HTTP/1.1", method="GET", path=path,
            headers=[("Host", "localhost")]))

        yield self.read_until_new_event(self.server_conn, self.dest_events)
        self.assertEqual(len(self.dest_events), 1)
        request, = self.dest_events.pop()
        self.assertIsInstance(request, HttpRequest)

        self.server_conn.send_response(HttpResponse(
            version="HTTP/1.1", code="200", reason="OK",
            headers=[("Content-Type", "plain/text")], body="body"))

        yield self.read_until_new_event(self.client_conn, self.src_events)
        self.assertEqual(len(self.src_events), 1)
        response, = self.src_events.pop()
        self.assertIsInstance(response, HttpResponse)

        self.client_stream.close()
        self.server_stream.close()
        self.http_layer.src_stream.close()
        self.http_layer.dest_stream.close()
        yield http_layer_future

    @gen_test
    def test_proxy_new_connection(self):
        prev_dest_stream = mock.Mock(**{
            "closed.return_value": False
        })
        self.http_layer.dest_stream = prev_dest_stream
        self.http_layer.context.host = "example.com"
        self.http_layer.context.port = 8080

        http_layer_future = self.http_layer.process_and_return_context()

        path = "http://127.0.0.1:{0}/".format(self.port)
        self.client_conn.send_request(HttpRequest(
            version="HTTP/1.1", method="GET", path=path,
            headers=[("Host", "localhost")]))

        yield self.wait_for_server_connect()
        yield self.read_until_new_event(self.server_conn, self.dest_events)
        self.assertEqual(len(self.dest_events), 1)
        request, = self.dest_events.pop()
        self.assertIsInstance(request, HttpRequest)

        self.server_conn.send_response(HttpResponse(
            version="HTTP/1.1", code="200", reason="OK",
            headers=[("Content-Type", "plain/text")], body="body"))

        yield self.read_until_new_event(self.client_conn, self.src_events)
        self.assertEqual(len(self.src_events), 1)
        response, = self.src_events.pop()
        self.assertIsInstance(response, HttpResponse)

        self.assertTrue(http_layer_future.running())

        self.client_conn.start_next_cycle()
        self.server_conn.start_next_cycle()

        self.client_conn.send_request(HttpRequest(
            version="HTTP/1.1", method="GET", path=path,
            headers=[("Host", "localhost")]))

        yield self.read_until_new_event(self.server_conn, self.dest_events)
        self.assertEqual(len(self.dest_events), 1)
        request, = self.dest_events.pop()
        self.assertIsInstance(request, HttpRequest)

        self.server_conn.send_response(HttpResponse(
            version="HTTP/1.1", code="200", reason="OK",
            headers=[("Content-Type", "plain/text")], body="body"))

        yield self.read_until_new_event(self.client_conn, self.src_events)
        self.assertEqual(len(self.src_events), 1)
        response, = self.src_events.pop()
        self.assertIsInstance(response, HttpResponse)

        prev_dest_stream.close.assert_called_with()

        self.client_stream.close()
        self.server_stream.close()
        self.http_layer.src_stream.close()
        self.http_layer.dest_stream.close()
        yield http_layer_future

    @gen_test
    def test_tunnel_on_http(self):
        http_layer_future = self.http_layer.process_and_return_context()
        path = "127.0.0.1:{0}".format(self.port)
        self.client_conn.send_request(HttpRequest(
            version="HTTP/1.1", method="CONNECT", path=path,
            headers=[
                ("Host", "127.0.0.1:{0}".format(self.port)),
                ("Proxy-Connection", "Keep-Alive"),
            ]))

        yield http_layer_future
        yield self.read_until_new_event(self.client_conn, self.src_events)
        self.assertEqual(len(self.src_events), 1)
        response, = self.src_events.pop()
        self.assertIsInstance(response, HttpResponse)
        self.assertEqual(response.code, "200")
        self.assertEqual(response.version, "HTTP/1.1")
        self.assertEqual(response.reason, "OK")

        yield http_layer_future

    def tearDown(self):
        self.client_stream.close()
        if self.server_stream:
            self.server_stream.close()
        self.http_layer.src_stream.close()
        if self.http_layer.dest_stream:
            self.http_layer.dest_stream.close()
        self.listener.close()
