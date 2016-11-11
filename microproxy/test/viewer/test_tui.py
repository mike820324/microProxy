import unittest
import mock
import gviewer
import tempfile
import json

from microproxy.context import ViewerContext, Event
from microproxy.version import VERSION
from microproxy.viewer.tui import Tui, LogDisplayer


class TestTui(unittest.TestCase):
    _VIEWER_CONTEXT = ViewerContext.deserialize({
        "host": "localhost",
        "port": 8080,
        "scheme": "https",
        "path": "/index",
        "version": VERSION,
        "client_tls": {
            "version": "TLSv1.2",
            "sni": "localhost",
            "cipher": "AES",
            "alpn": "http/1.1",
        },
        "server_tls": {
            "version": "TLSv1.1",
            "sni": "localhost",
            "cipher": "AES",
            "alpn": "http/1.1",
        },
        "request": {
            "method": "GET",
            "path": "/index",
            "version": "HTTP/1.1",
            "headers": [
                ("Content-Type", "application/json"),
                ("Accept", "application/json"),
            ],
            "body": "body".encode("base64"),
        },
        "response": {
            "code": "200",
            "reason": "OK",
            "version": "HTTP/1.1",
            "headers": [
                ("Content-Type", "application/json"),
                ("Accept", "application/json"),
            ],
            "body": "body".encode("base64"),
        },
    })

    def setUp(self):
        self.mocks = mock.Mock()

        self.config = {
            "viewer_channel": "tcp://localhost:5581",
            "events_channel": "tcp://localhost:5582",
        }

        self.tui = Tui(
            self.config, stream=self.mocks.stream,
            event_loop=self.mocks.event_loop)
        self.tui.formmater = self

    def format_body(self, body, headers):
        return gviewer.Text(body)

    def test_get_views(self):
        views = self.tui.get_views()

        self.assertIsInstance(views, list)
        self.assertEqual(len(views), 3)

        self.assertEqual(views[0], ("Request", self.tui.request_view))
        self.assertEqual(views[1], ("Response", self.tui.response_view))
        self.assertEqual(views[2], ("Detail", self.tui.detail_view))

    def test_request_view(self):
        view = self.tui.request_view(self._VIEWER_CONTEXT)

        self.assertIsInstance(view, gviewer.View)
        self.assertEqual(len(view.groups), 3)

        # verify summary
        summary_group = view.groups[0]
        self.assertIsInstance(summary_group, gviewer.PropsGroup)
        self.assertEqual(str(summary_group), (
            "\n"
            "method  : GET\n"
            "path    : /index\n"
            "version : HTTP/1.1"
        ))

        # verify headers
        headers_group = view.groups[1]
        self.assertIsInstance(headers_group, gviewer.PropsGroup)
        self.assertEqual(str(headers_group), (
            "Request Header\n"
            "Content-Type : application/json\n"
            "Accept       : application/json"
        ))

        # verify body
        body_group = view.groups[2]
        self.assertIsInstance(body_group, gviewer.Group)
        self.assertEqual(str(body_group), (
            "Request Body\n"
            "body"
        ))

    def test_response_view(self):
        view = self.tui.response_view(self._VIEWER_CONTEXT)

        self.assertIsInstance(view, gviewer.View)
        self.assertEqual(len(view.groups), 3)

        # verify summary
        summary_group = view.groups[0]
        self.assertIsInstance(summary_group, gviewer.PropsGroup)
        self.assertEqual(str(summary_group), (
            "\n"
            "code    : 200\n"
            "reason  : OK\n"
            "version : HTTP/1.1"
        ))

        # verify headers
        headers_group = view.groups[1]
        self.assertIsInstance(headers_group, gviewer.PropsGroup)
        self.assertEqual(str(headers_group), (
            "Response Header\n"
            "Content-Type : application/json\n"
            "Accept       : application/json"
        ))

        # verify body
        body_group = view.groups[2]
        self.assertIsInstance(body_group, gviewer.Group)
        self.assertEqual(str(body_group), (
            "Response Body\n"
            "body"
        ))

    def test_detail_view(self):
        view = self.tui.detail_view(self._VIEWER_CONTEXT)

        self.assertIsInstance(view, gviewer.View)
        self.assertEqual(len(view.groups), 3)

        # verify summary
        summary_group = view.groups[0]
        self.assertIsInstance(summary_group, gviewer.PropsGroup)
        self.assertEqual(str(summary_group), (
            "Detail\n"
            "Host : localhost\n"
            "Port : 8080\n"
            "Path : /index"
        ))

        # verify client tls
        client_tls_group = view.groups[1]
        self.assertIsInstance(client_tls_group, gviewer.PropsGroup)
        self.assertEqual(str(client_tls_group), (
            "Client Connection\n"
            "TLS Version          : TLSv1.2\n"
            "Server Name Notation : localhost\n"
            "Cipher               : AES\n"
            "ALPN                 : http/1.1"
        ))

        # verify server tls
        server_tls_group = view.groups[2]
        self.assertIsInstance(server_tls_group, gviewer.PropsGroup)
        self.assertEqual(str(server_tls_group), (
            "Server Connection\n"
            "TLS Version          : TLSv1.1\n"
            "Server Name Notation : localhost\n"
            "Cipher               : AES\n"
            "ALPN                 : http/1.1"
        ))

    def test_export_replay(self):
        _, out_file = tempfile.mkstemp()
        self.config["out_file"] = out_file
        self.tui.export_replay(self.mocks.parent, self._VIEWER_CONTEXT, self.mocks.widget)

        with open(out_file, "r") as f:
            ctx = ViewerContext.deserialize(json.load(f))
        self.assertIsNotNone(ctx.request)
        self.assertIsNotNone(ctx.response)
        self.assertIsNotNone(ctx.client_tls)
        self.assertIsNotNone(ctx.server_tls)

        self.mocks.widget.set_title.assert_called_with(
            self.tui.summary(self._VIEWER_CONTEXT, exported=True))

        self.mocks.parent.notify.assert_called_with(
            "replay script export to {0}".format(out_file))

    def test_summary(self):
        self.tui.terminal_width = 100
        summary = self.tui.summary(self._VIEWER_CONTEXT)
        self.assertEqual(
            summary,
            [("indicator", "  "),
             ("code ok", "200"),
             (" GET     https://localhost:8080/index")]
        )

    def test_replay(self):
        self.tui.event_client = self.mocks.event_client
        self.tui.replay(self.mocks.parent, self._VIEWER_CONTEXT)

        self.mocks.event_client.send_event.assert_called_with(
            Event("replay", self._VIEWER_CONTEXT))
        self.mocks.parent.notify.assert_called_with("sent replay event to server")

    def test_execute_replay(self):
        self.tui.event_client = self.mocks.event_client
        self.tui.execute_replay(self._VIEWER_CONTEXT)

        self.mocks.event_client.send_event.assert_called_with(
            Event("replay", self._VIEWER_CONTEXT))

    def test_start_with_replay(self):
        self.tui.viewer = self.mocks.viewer
        self.tui.event_client = self.mocks.event_client
        self.config["replay_file"] = "microproxy/test/data/replay.script"

        self.tui.start()
        self.mocks.event_client.send_event.assert_has_calls([
            mock.call(_IsEventContext()),
            mock.call(_IsEventContext())])
        self.mocks.viewer.start.assert_called_with()

    def test_code_text_markup_ok(self):
        self.assertEquals(
            self.tui._code_text_markup(200),
            ("code ok", "200"))

    def test_code_text_markup_error(self):
        self.assertEquals(
            self.tui._code_text_markup(500),
            ("code error", "500"))

    def test_format_port_default(self):
        self.assertEquals(
            self.tui._format_port("https", 443), "")
        self.assertEquals(
            self.tui._format_port("http", 80), "")

    def test_format_port(self):
        self.assertEquals(
            self.tui._format_port("http", 8080), ":8080")

    def test_open_log(self):
        self.tui.log(self.mocks.controller, None, None)
        self.mocks.controller.open_view_by_context.assert_called_with(
            self.tui.log_context)


class _IsEventContext(object):
    def __eq__(self, other):
        return isinstance(other, Event)


class TestLogDisplayer(unittest.TestCase):
    def setUp(self):
        self.mocks = mock.Mock()

        self.config = {
            "viewer_channel": "tcp://localhost:5581",
        }

        self.log_displayer = LogDisplayer(
            self.config, stream=self.mocks.stream)

    def test_summary_without_line_break(self):
        self.assertEqual(
            self.log_displayer.summary(("logger", "this is log message")),
            "this is log message")

    def test_summary_with_line_break(self):
        self.assertEqual(
            self.log_displayer.summary(("logger", "this is log message\nsecond line")),
            "this is log message")

    def test_get_views(self):
        self.assertEquals(
            self.log_displayer.get_views(),
            [("", self.log_displayer.show)])

    def test_show(self):
        view = self.log_displayer.show(("logger", "this is log message\nsecond line"))

        self.assertIsInstance(view, gviewer.View)
        self.assertEqual(
            str(view),
            ("\nthis is log message\nsecond line\n"))
