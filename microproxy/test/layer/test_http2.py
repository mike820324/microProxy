import mock

from tornado.testing import gen_test
from tornado.gen import coroutine

from microproxy.test.utils import ProxyAsyncTestCase
from microproxy.context import LayerContext, ServerContext
from microproxy.layer import Http2Layer
from microproxy.protocol.http2 import Connection
from microproxy.context import HttpRequest, HttpResponse, HttpHeaders


class TestHttp2Layer(ProxyAsyncTestCase):
    def setUp(self):
        super(TestHttp2Layer, self).setUp()
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

        self.http_layer = Http2Layer(
            server_state,
            LayerContext(mode="socks",
                         src_stream=src_stream,
                         dest_stream=dest_stream))

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
        self.client_conn = Connection(
            self.client_stream, client_side=True,
            on_response=self.record_src_event,
            on_unhandled=self.ignore_event)
        self.server_conn = Connection(
            self.server_stream, client_side=False,
            on_request=self.record_dest_event,
            on_unhandled=self.ignore_event)

        result_future = self.http_layer.process_and_return_context()
        self.client_conn.initiate_connection()
        self.server_conn.initiate_connection()

        self.client_conn.send_request(
            1, HttpRequest(headers=[
                (":method", "GET"),
                (":path", "/"),
                ("host", "mpserver")]))

        yield self.read_until_new_event(self.server_conn, self.dest_events)

        self.server_conn.send_response(
            1, HttpResponse(headers=[(":status", "200"), ("host", "mpserver")],
                            body=b"ccc"))

        yield self.read_until_new_event(self.client_conn, self.src_events)

        self.client_stream.close()
        self.server_stream.close()

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
                         ("host", "mpserver")]))
        self.assertEqual(response.body, b"ccc")

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
                         ("host", "mpserver")]))

    @gen_test
    def test_req_with_priority_updated(self):
        self.client_conn = Connection(
            self.client_stream, client_side=True,
            on_unhandled=self.ignore_event)
        self.server_conn = Connection(
            self.server_stream, client_side=False,
            on_request=self.record_dest_event,
            on_unhandled=self.ignore_event)

        result_future = self.http_layer.process_and_return_context()
        self.client_conn.initiate_connection()
        self.server_conn.initiate_connection()

        self.client_conn.send_request(
            1, HttpRequest(headers=[
                (":method", "GET"),
                (":path", "/"),
                ("host", "mpserver")]),
            priority_weight=10,
            priority_depends_on=0,
            priority_exclusive=False)

        yield self.read_until_new_event(self.server_conn, self.dest_events)

        self.client_stream.close()
        self.server_stream.close()

        yield result_future

        self.assertEqual(len(self.dest_events), 1)
        stream_id, request, priority_updated = self.dest_events[0]
        self.assertEqual(stream_id, 1)
        self.assertEqual(request.method, "GET")
        self.assertEqual(request.path, "/")
        self.assertEqual(request.version, "HTTP/2")
        self.assertEqual(
            request.headers,
            HttpHeaders([(":method", "GET"),
                         (":path", "/"),
                         ("host", "mpserver")]))
        self.assertIsNotNone(priority_updated)
        self.assertEqual(priority_updated.weight, 10)
        self.assertEqual(priority_updated.exclusive, False)
        self.assertEqual(priority_updated.depends_on, 0)

    @gen_test
    def test_push(self):
        self.client_conn = Connection(
            self.client_stream, client_side=True,
            on_response=self.record_src_event,
            on_push=self.record_src_event,
            on_unhandled=self.ignore_event)
        self.server_conn = Connection(
            self.server_stream, client_side=False,
            on_request=self.record_dest_event,
            on_unhandled=self.ignore_event)

        result_future = self.http_layer.process_and_return_context()
        self.client_conn.initiate_connection()
        self.server_conn.initiate_connection()

        self.client_conn.send_request(
            1, HttpRequest(headers=[
                (":method", "GET"),
                (":path", "/"),
                ("Host", "mpserver")]))

        yield self.read_until_new_event(self.server_conn, self.dest_events)

        self.server_conn.send_pushed_stream(1, 2, HttpRequest(
            headers=[(":method", "GET"), (":path", "/resource")]))
        yield self.read_until_new_event(self.client_conn, self.src_events)

        self.server_conn.send_response(
            2, HttpResponse(headers=[(":status", "200"), ("aaa", "bbb")],
                            body=b"ccc"))
        yield self.read_until_new_event(self.client_conn, self.src_events)

        self.client_stream.close()
        self.server_stream.close()

        yield result_future

        self.assertEqual(len(self.src_events), 2)
        stream_id, parent_stream_id, request = self.src_events[0]
        self.assertEqual(stream_id, 2)
        self.assertEqual(parent_stream_id, 1)
        self.assertEqual(request.method, "GET")
        self.assertEqual(request.path, "/resource")
        self.assertEqual(request.version, "HTTP/2")
        self.assertEqual(
            request.headers,
            HttpHeaders([(":method", "GET"),
                         (":path", "/resource")]))

        stream_id, response = self.src_events[1]
        self.assertEqual(stream_id, 2)
        self.assertEqual(response.code, "200")
        self.assertEqual(response.version, "HTTP/2")
        self.assertEqual(
            response.headers,
            HttpHeaders([(":status", "200"),
                         ("aaa", "bbb")]))

    @gen_test
    def test_window_updates(self):
        self.client_conn = Connection(
            self.client_stream, client_side=True,
            on_window_updates=self.record_src_event,
            on_unhandled=self.ignore_event)
        self.server_conn = Connection(
            self.server_stream, client_side=False,
            on_window_updates=self.record_dest_event,
            on_unhandled=self.ignore_event)

        result_future = self.http_layer.process_and_return_context()
        self.client_conn.initiate_connection()
        self.server_conn.initiate_connection()

        self.client_conn.send_window_updates(0, 100)
        yield self.read_until_new_event(self.server_conn, self.dest_events)

        self.client_conn.send_request(
            1, HttpRequest(headers=[
                (":method", "GET"),
                (":path", "/"),
                ("Host", "mpserver")]))
        self.client_conn.send_window_updates(1, 200)
        yield self.read_until_new_event(self.server_conn, self.dest_events)

        self.server_conn.send_window_updates(1, 300)
        yield self.read_until_new_event(self.client_conn, self.src_events)

        self.client_stream.close()
        self.server_stream.close()

        yield result_future
        print self.src_events
        self.assertEqual(len(self.src_events), 1)
        self.assertEqual(self.src_events[0], (1, 300))
        self.assertEqual(len(self.dest_events), 2)
        self.assertEqual(self.dest_events[0], (0, 100))
        self.assertEqual(self.dest_events[1], (1, 200))

    @gen_test
    def test_priority_updated(self):
        self.client_conn = Connection(
            self.client_stream, client_side=True,
            on_unhandled=self.ignore_event)
        self.server_conn = Connection(
            self.server_stream, client_side=False,
            on_priority_updates=self.record_dest_event,
            on_unhandled=self.ignore_event)

        result_future = self.http_layer.process_and_return_context()
        self.client_conn.initiate_connection()
        self.server_conn.initiate_connection()

        self.client_conn.send_request(
            1, HttpRequest(headers=[
                (":method", "GET"),
                (":path", "/"),
                ("Host", "mpserver")]))
        self.client_conn.send_priority_updates(1, 0, 10, False)
        yield self.read_until_new_event(self.server_conn, self.dest_events)

        self.client_stream.close()
        self.server_stream.close()

        yield result_future
        self.assertEqual(len(self.dest_events), 1)
        self.assertEqual(self.dest_events[0], (1, 0, 10, False))

    @gen_test
    def test_reset(self):
        self.client_conn = Connection(
            self.client_stream, client_side=True,
            on_reset=self.record_src_event,
            on_unhandled=self.ignore_event)
        self.server_conn = Connection(
            self.server_stream, client_side=False,
            on_request=self.record_dest_event,
            on_reset=self.record_dest_event,
            on_unhandled=self.ignore_event)

        result_future = self.http_layer.process_and_return_context()
        self.client_conn.initiate_connection()
        self.server_conn.initiate_connection()

        self.client_conn.send_request(
            1, HttpRequest(headers=[
                (":method", "GET"),
                (":path", "/"),
                ("Host", "mpserver")]))
        yield self.read_until_new_event(self.server_conn, self.dest_events)

        self.client_conn.send_reset(1, 0)
        yield self.read_until_new_event(self.server_conn, self.dest_events)

        self.client_conn.send_request(
            3, HttpRequest(headers=[
                (":method", "GET"),
                (":path", "/"),
                ("Host", "mpserver")]))
        yield self.read_until_new_event(self.server_conn, self.dest_events)

        self.server_conn.send_reset(3, 0)
        yield self.read_until_new_event(self.client_conn, self.src_events)

        self.client_stream.close()
        self.server_stream.close()

        yield result_future
        self.assertEqual(len(self.src_events), 1)
        self.assertEqual(self.src_events[0], (3, 0))
        self.assertEqual(len(self.dest_events), 3)  # NOTE: req, reset, req
        self.assertEqual(self.dest_events[1], (1, 0))

    @gen_test
    def test_src_send_terminate(self):
        self.client_conn = Connection(
            self.client_stream, client_side=True,
            on_unhandled=self.ignore_event)
        self.server_conn = Connection(
            self.server_stream, client_side=False,
            on_terminate=self.record_dest_event,
            on_unhandled=self.ignore_event)

        result_future = self.http_layer.process_and_return_context()
        self.client_conn.initiate_connection()
        self.server_conn.initiate_connection()

        self.client_conn.send_terminate()
        yield self.read_until_new_event(self.server_conn, self.dest_events)

        self.client_stream.close()
        self.server_stream.close()

        yield result_future
        self.assertEqual(len(self.dest_events), 1)
        self.assertEqual(self.dest_events[0], (None, 0, 0))

    @gen_test
    def test_dest_send_terminate(self):
        self.client_conn = Connection(
            self.client_stream, client_side=True,
            on_terminate=self.record_src_event,
            on_settings=self.record_src_event,
            on_unhandled=self.ignore_event)
        self.server_conn = Connection(
            self.server_stream, client_side=False,
            on_unhandled=self.ignore_event)

        result_future = self.http_layer.process_and_return_context()
        self.client_conn.initiate_connection()
        self.server_conn.initiate_connection()

        # NOTE: because hyper-h2 will always send SettingsChanged when init
        # Than client will receive two setting frame from destination and server
        yield self.read_until_new_event(self.client_conn, self.src_events)
        yield self.read_until_new_event(self.client_conn, self.src_events)

        self.server_conn.send_terminate()
        yield self.read_until_new_event(self.client_conn, self.src_events)

        self.client_stream.close()
        self.server_stream.close()

        yield result_future
        self.assertEqual(len(self.src_events), 3)
        self.assertEqual(self.src_events[2], (None, 0, 0))

    @gen_test
    def test_safe_mapping_id(self):
        self.client_conn = Connection(
            self.client_stream, client_side=True,
            on_unhandled=self.ignore_event)
        self.server_conn = Connection(
            self.server_stream, client_side=False,
            on_request=self.record_dest_event,
            on_unhandled=self.ignore_event)

        result_future = self.http_layer.process_and_return_context()
        self.client_conn.initiate_connection()
        self.server_conn.initiate_connection()

        self.assertEqual(
            self.http_layer.safe_mapping_id(self.http_layer.src_to_dest_ids, 1), 0)

        self.client_conn.send_request(
            1, HttpRequest(headers=[
                (":method", "GET"),
                (":path", "/"),
                ("aaa", "bbb")]))
        yield self.read_until_new_event(self.server_conn, self.dest_events)

        self.assertEqual(
            self.http_layer.safe_mapping_id(self.http_layer.src_to_dest_ids, 1), 1)

        self.client_stream.close()
        self.server_stream.close()
        yield result_future

    @gen_test
    def test_replay(self):
        self.http_layer.context.mode = "replay"
        self.client_conn = Connection(
            self.client_stream, client_side=True,
            on_unhandled=self.ignore_event)
        self.server_conn = Connection(
            self.server_stream, client_side=False,
            on_request=self.record_dest_event,
            on_unhandled=self.ignore_event)

        result_future = self.http_layer.process_and_return_context()
        self.client_conn.initiate_connection()
        self.server_conn.initiate_connection()

        self.client_conn.send_request(
            1, HttpRequest(headers=[
                (":method", "GET"),
                (":path", "/"),
                ("host", "mpserver")]))

        yield self.read_until_new_event(self.server_conn, self.dest_events)

        self.server_conn.send_response(
            1, HttpResponse(headers=[(":status", "200"), ("host", "mpserver")],
                            body=b"ccc"))

        result = yield result_future

        self.assertIsNotNone(result)
        self.assertIsInstance(result, LayerContext)

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
                         ("host", "mpserver")]))

    def tearDown(self):
        self.client_stream.close()
        self.server_stream.close()
        self.http_layer.src_stream.close()
        self.http_layer.dest_stream.close()
