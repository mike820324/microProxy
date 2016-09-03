import mock
import h11
from tornado.testing import AsyncTestCase, gen_test
from tornado.concurrent import Future
from tornado.gen import coroutine

from microproxy.event.replay import ReplayHandler
from microproxy.protocol.http1 import Connection as Http1Connection
from microproxy.protocol.http2 import Connection as Http2Connection
from microproxy.context import HttpRequest, HttpHeaders


class TestReplayHandler(AsyncTestCase):
    def setUp(self):
        super(TestReplayHandler, self).setUp()
        self.layer_manager = mock.Mock()
        self.layer_manager.get_first_layer = mock.Mock(
            return_value=self.layer_manager.first_layer)
        self.layer_manager.run_layers = mock.Mock(
            side_effect=self.get_context)
        self.replay_handler = ReplayHandler(
            dict(), interceptor=mock.Mock(), layer_manager=self.layer_manager)
        self.context = None
        self.http_events = []

    def _future(self, result):
        future = Future()
        future.set_result(result)
        return future

    def get_context(self, layer, context):
        self.context = context
        return self._future(None)

    def collect_event(self, *args):
        self.http_events.append(args)

    @coroutine
    def read_until(self, conn, count):
        while len(self.http_events) < count:
            yield conn.read_bytes()

    @gen_test
    def test_http1(self):
        event = dict(
            host="localhost", port=8080, scheme="http", path="/",
            request=dict(
                method="GET", path="/", version="HTTP/1.1",
                headers=[("Host", "localhost")]),
            response=None)
        yield self.replay_handler.handle(event)

        self.assertIsNotNone(self.context)
        self.layer_manager.get_first_layer.assert_called_with(
            self.context)
        self.layer_manager.run_layers.assert_called_with(
            self.layer_manager.first_layer, self.context)

        conn = Http1Connection(
            h11.SERVER, self.context.src_stream, on_unhandled=self.collect_event)
        yield self.read_until(conn, 1)

        req, = self.http_events[0]
        self.assertIsInstance(req, HttpRequest)
        self.assertEqual(req.method, "GET")
        self.assertEqual(req.version, "HTTP/1.1")
        self.assertEqual(req.path, "/")
        self.assertEqual(req.headers, HttpHeaders([
            ("Host", "localhost")]))

    @gen_test
    def test_http2(self):
        event = dict(
            host="localhost", port=8080, scheme="h2", path="/",
            request=dict(
                method="GET", path="/", version="HTTP/2",
                headers=[(":method", "GET"), (":path", "/")]),
            response=None)
        yield self.replay_handler.handle(event)

        self.assertIsNotNone(self.context)
        self.layer_manager.get_first_layer.assert_called_with(
            self.context)
        self.layer_manager.run_layers.assert_called_with(
            self.layer_manager.first_layer, self.context)

        conn = Http2Connection(
            self.context.src_stream, client_side=False, on_request=self.collect_event, on_unhandled=mock.Mock())
        yield self.read_until(conn, 1)

        _, req, _ = self.http_events[0]
        self.assertIsInstance(req, HttpRequest)
        self.assertEqual(req.method, "GET")
        self.assertEqual(req.version, "HTTP/2")
        self.assertEqual(req.path, "/")
        self.assertEqual(req.headers, HttpHeaders([
            (":method", "GET"), (":path", "/")]))