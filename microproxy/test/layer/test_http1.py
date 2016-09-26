from mock import Mock
import h11

from tornado.testing import gen_test
from tornado.gen import coroutine

from microproxy.test.utils import ProxyAsyncTestCase
from microproxy.context import LayerContext, ServerContext
from microproxy.layer import Http1Layer
from microproxy.protocol.http1 import Connection
from microproxy.context import HttpRequest, HttpResponse, HttpHeaders
from microproxy.exception import SrcStreamClosedError, DestStreamClosedError


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

        self.context = LayerContext(mode="socks",
                                    src_stream=src_stream,
                                    dest_stream=dest_stream)

        interceptor = Mock()
        interceptor.publish = Mock(return_value=None)
        interceptor.request = Mock(return_value=None)
        interceptor.response = Mock(return_value=None)
        server_state = ServerContext(interceptor=interceptor)

        self.http_layer = Http1Layer(server_state, self.context)

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
        curr_count = len(events)
        while curr_count == len(events):
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
        self.assertEqual(request.headers, HttpHeaders([("Host", "localhost")]))

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
        self.context.src_stream.close()
        self.context.dest_stream.close()
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
        request, = self.dest_events[0]
        self.assertIsInstance(request, HttpRequest)
        self.assertEqual(request.method, "GET")
        self.assertEqual(request.version, "HTTP/1.1")
        self.assertEqual(request.path, "/index")
        self.assertEqual(request.headers, HttpHeaders([("Host", "localhost")]))

        self.client_stream.close()

        self.server_conn.send_response(HttpResponse(
            version="HTTP/1.1", code="200", reason="OK",
            headers=[("Content-Type", "plain/text")]))

        with self.assertRaises(SrcStreamClosedError):
            yield http_layer_future

    @gen_test
    def test_replay(self):
        self.context.mode = "replay"

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
        self.assertEqual(request.headers, HttpHeaders([("Host", "localhost")]))

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

        self.assertTrue(http_layer_future.done())

        yield http_layer_future
        self.assertTrue(self.context.src_stream.closed())
        self.assertTrue(self.context.dest_stream.closed())

    @gen_test
    def test_on_websocket(self):
        http_layer_future = self.http_layer.process_and_return_context()

        self.client_conn.send_request(HttpRequest(
            version="HTTP/1.1", method="GET", path="/chat",
            headers=[("Host", "localhost"), ("Upgrade", "websocket")]))

        yield self.read_until_new_event(self.server_conn, self.dest_events)
        self.assertEqual(len(self.dest_events), 1)
        request, = self.dest_events[0]
        self.assertIsInstance(request, HttpRequest)
        self.assertEqual(request.method, "GET")
        self.assertEqual(request.version, "HTTP/1.1")
        self.assertEqual(request.path, "/chat")
        self.assertEqual(request.headers,
                         HttpHeaders([("Host", "localhost"),
                                      ("Upgrade", "websocket")]))

        self.server_conn.send_info_response(HttpResponse(
            version="HTTP/1.1", code="101", reason="Switching Protocol",
            headers=[("Upgrade", "websocket"), ("Connection", "Upgrade")]))

        yield self.read_until_new_event(self.client_conn, self.src_events)
        self.assertEqual(len(self.src_events), 1)
        response, = self.src_events[0]
        self.assertIsInstance(response, HttpResponse)
        self.assertEqual(response.code, "101")
        self.assertEqual(response.version, "HTTP/1.1")
        self.assertEqual(response.reason, "Switching Protocol")
        self.assertEqual(
            response.headers,
            HttpHeaders([("Upgrade", "websocket"), ("Connection", "Upgrade")]))

        self.assertTrue(http_layer_future.done())
        yield http_layer_future
        self.assertFalse(self.context.src_stream.closed())
        self.assertFalse(self.context.dest_stream.closed())

    @gen_test
    def test_read_response_without_chunked_and_content_length(self):
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
        self.assertEqual(request.headers, HttpHeaders([("Host", "localhost")]))

        yield self.server_stream.write(
            (b"HTTP/1.1 200 OK\r\n"
             b"Connection: closed\r\n\r\n"
             b"body"))

        self.server_stream.close()

        yield self.read_until_new_event(self.client_conn, self.src_events)
        self.assertEqual(len(self.src_events), 1)
        response, = self.src_events[0]
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
        request, = self.dest_events[0]
        self.assertIsInstance(request, HttpRequest)
        self.assertEqual(request.method, "GET")
        self.assertEqual(request.version, "HTTP/1.1")
        self.assertEqual(request.path, "/chat")
        self.assertEqual(request.headers, HttpHeaders([("Host", "localhost"), ("Upgrade", "websocket")]))

        self.client_stream.close()

        self.server_conn.send_info_response(HttpResponse(
            version="HTTP/1.1", code="101", reason="Switching Protocol",
            headers=[("Content-Type", "plain/text")]))

        with self.assertRaises(SrcStreamClosedError):
            yield http_layer_future

    def tearDown(self):
        self.client_stream.close()
        self.server_stream.close()
        self.context.src_stream.close()
        self.context.dest_stream.close()
