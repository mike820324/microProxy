import socket
import mock
from datetime import timedelta
from tornado import gen
from tornado.testing import AsyncTestCase, gen_test, bind_unused_port
from tornado.locks import Event
from tornado.iostream import IOStream
from tornado.netutil import add_accept_handler

from microproxy.protocol.http2 import Connection
from microproxy.context import HttpRequest, HttpResponse, HttpHeaders


class TestConnection(AsyncTestCase):
    def setUp(self):
        super(TestConnection, self).setUp()
        self.asyncSetUp()
        self.request = None
        self.response = None
        self.settings = None
        self.window_updates = None
        self.priority_updates = None
        self.push = None
        self.reset = None

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
        self.request = (stream_id, request)

    def on_response(self, stream_id, response):
        self.response = (stream_id, response)

    def on_settings(self, settings):
        self.settings = settings

    def on_window_updates(self, stream_id, delta):
        self.window_updates = (stream_id, delta)

    def on_priority_updates(self, stream_id, depends_on,
                            weight, exclusive):
        self.priority_updates = dict(
            stream_id=stream_id, depends_on=depends_on,
            weight=weight, exclusive=exclusive)

    def on_push(self, pushed_stream_id, parent_stream_id, request):
        self.push = dict(
            pushed_stream_id=pushed_stream_id,
            parent_stream_id=parent_stream_id,
            request=request)

    def on_reset(self, stream_id, error_code):
        self.reset = (stream_id, error_code)

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
        yield server_conn.read_bytes()

        self.assertIsNotNone(self.request)
        _, request = self.request
        self.assertEqual(request.headers,
                         HttpHeaders([
                             (":method", "GET"),
                             (":path", "/"),
                             ("aaa", "bbb")]))
        self.assertEqual(request.method, "GET")
        self.assertEqual(request.path, "/")
        self.assertEqual(request.version, "HTTP/2")

    @gen_test
    def test_on_response(self):
        client_conn = Connection(
            self.client_stream, client_side=True, on_response=self.on_response,
            on_unhandled=mock.Mock())
        client_conn.initiate_connection()
        client_conn.send_request(
            client_conn.get_next_available_stream_id(),
            HttpRequest(headers=[
                (":method", "GET"),
                (":path", "/"),
                ("aaa", "bbb")]))

        server_conn = Connection(
            self.server_stream, client_side=False,
            on_request=self.on_request, on_unhandled=mock.Mock())
        server_conn.initiate_connection()
        yield server_conn.read_bytes()
        server_conn.send_response(
            self.request[0],
            HttpResponse(
                headers=[(":status", "200"),
                         ("aaa", "bbb")],
                body=b"ccc"))

        yield client_conn.read_bytes()

        self.assertIsNotNone(self.response)
        _, response = self.response
        self.assertEqual(response.headers,
                         HttpHeaders([
                             (":status", "200"),
                             ("aaa", "bbb")]))
        self.assertEqual(response.code, "200")
        self.assertEqual(response.version, "HTTP/2")

    @gen_test
    def test_on_settings(self):
        client_conn = Connection(
            self.client_stream, client_side=True, on_unhandled=mock.Mock())
        client_conn.initiate_connection()

        server_conn = Connection(
            self.server_stream, client_side=False, on_settings=self.on_settings)
        server_conn.initiate_connection()
        yield server_conn.read_bytes()

        # NOTE: h11 initiate_connection will send default settings
        self.assertIsNotNone(self.settings)

        self.settings = None
        client_conn.send_update_settings({
            4: 11111, 5: 22222})

        yield server_conn.read_bytes()
        self.assertIsNotNone(self.settings)
        new_settings = {id: cs.new_value for (id, cs) in self.settings.iteritems()}
        self.assertEqual(new_settings, {4: 11111, 5: 22222})

    @gen_test
    def test_on_window_updates(self):
        client_conn = Connection(
            self.client_stream, client_side=True, on_unhandled=mock.Mock())
        client_conn.initiate_connection()
        client_conn.send_window_updates(
            0, 100)

        server_conn = Connection(
            self.server_stream, client_side=False, on_settings=self.on_settings,
            on_window_updates=self.on_window_updates)
        server_conn.initiate_connection()
        yield server_conn.read_bytes()
        self.assertIsNotNone(self.window_updates)
        self.assertEqual(self.window_updates, (0, 100))

    @gen_test
    def test_on_priority_updates(self):
        client_conn = Connection(
            self.client_stream, client_side=True, on_unhandled=mock.Mock())
        client_conn.initiate_connection()
        stream_id = client_conn.get_next_available_stream_id()
        client_conn.send_request(
            stream_id,
            HttpRequest(headers=[
                (":method", "GET"),
                (":path", "/"),
                ("aaa", "bbb")]))
        client_conn.send_priority_updates(
            stream_id, 0, 10, False)

        server_conn = Connection(
            self.server_stream, client_side=False,
            on_priority_updates=self.on_priority_updates,
            on_unhandled=mock.Mock())
        server_conn.initiate_connection()
        yield server_conn.read_bytes()
        self.assertIsNotNone(self.priority_updates)
        self.assertEqual(
            self.priority_updates,
            dict(stream_id=stream_id, depends_on=0, weight=10, exclusive=False))

    @gen_test
    def test_on_pushed_stream(self):
        client_conn = Connection(
            self.client_stream, client_side=True, on_push=self.on_push,
            on_unhandled=mock.Mock())
        client_conn.initiate_connection()
        client_conn.send_request(
            client_conn.get_next_available_stream_id(),
            HttpRequest(headers=[
                (":method", "GET"),
                (":path", "/")]))

        server_conn = Connection(
            self.server_stream, client_side=False, on_request=self.on_request,
            on_unhandled=mock.Mock())
        server_conn.initiate_connection()
        yield server_conn.read_bytes()
        stream_id, _ = self.request
        server_conn.send_pushed_stream(
            stream_id,
            2,
            HttpRequest(headers=[
                (":method", "GET"),
                (":path", "/resource")]))

        yield client_conn.read_bytes()
        self.assertIsNotNone(self.push)
        self.assertEqual(self.push["parent_stream_id"], 1)
        self.assertEqual(self.push["pushed_stream_id"], 2)
        self.assertEqual(
            self.push["request"].headers,
            HttpHeaders([
                (":method", "GET"),
                (":path", "/resource")]))

    @gen_test
    def test_on_reset(self):
        client_conn = Connection(
            self.client_stream, client_side=True, on_reset=self.on_reset,
            on_unhandled=mock.Mock())
        client_conn.initiate_connection()
        client_conn.send_request(
            client_conn.get_next_available_stream_id(),
            HttpRequest(headers=[
                (":method", "GET"),
                (":path", "/")]))

        server_conn = Connection(
            self.server_stream, client_side=False, on_request=self.on_request,
            on_unhandled=mock.Mock())
        yield server_conn.read_bytes()
        stream_id, _ = self.request
        server_conn.send_reset(stream_id, 2)

        yield client_conn.read_bytes()
        self.assertIsNotNone(self.reset)
        self.assertEqual(self.reset, (stream_id, 2))

    @gen_test
    def test_on_terminate(self):
        client_conn = Connection(
            self.client_stream, client_side=True, on_unhandled=mock.Mock())
        client_conn.initiate_connection()

        on_terminate = mock.Mock()
        server_conn = Connection(
            self.server_stream, client_side=False, on_terminate=on_terminate,
            on_unhandled=mock.Mock())
        server_conn.initiate_connection()

        yield server_conn.read_bytes()
        client_conn.send_terminate()
        yield server_conn.read_bytes()

        on_terminate.assert_called_with(None, 0, 0)

    @gen_test
    def test_on_post_request(self):
        client_conn = Connection(self.client_stream, client_side=True)
        client_conn.initiate_connection()
        client_conn.send_request(
            client_conn.get_next_available_stream_id(),
            HttpRequest(headers=[
                (":method", "POST"),
                (":path", "/"),
                ("aaa", "bbb")], body=b"aaaa"))

        server_conn = Connection(
            self.server_stream, client_side=False, on_request=self.on_request,
            on_settings=self.on_settings)
        server_conn.initiate_connection()
        yield server_conn.read_bytes()

        self.assertIsNotNone(self.request)
        _, request = self.request
        self.assertEqual(request.headers,
                         HttpHeaders([
                             (":method", "POST"),
                             (":path", "/"),
                             ("aaa", "bbb")]))
        self.assertEqual(request.method, "POST")
        self.assertEqual(request.path, "/")
        self.assertEqual(request.version, "HTTP/2")
        self.assertEqual(request.body, b"aaaa")

    @gen_test
    def test_readonly(self):
        client_conn = Connection(self.client_stream, client_side=True, readonly=True)
        client_conn.initiate_connection()
        client_conn.send_request(
            client_conn.get_next_available_stream_id(),
            HttpRequest(headers=[
                (":method", "GET"),
                (":path", "/"),
                ("aaa", "bbb")]))

        with self.assertRaises(gen.TimeoutError):
            yield gen.with_timeout(
                timedelta(milliseconds=100),
                self.server_stream.read_bytes(1))

    def tearDown(self):
        self.client_stream.close()
        self.server_stream.close()
