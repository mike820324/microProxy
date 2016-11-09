import zmq
from zmq.eventloop import ioloop, zmqstream
import urwid
import json
from backports.shutil_get_terminal_size import get_terminal_size

import gviewer

from microproxy.context import ViewerContext, Event
from microproxy.event import EventClient, REPLAY
from microproxy.viewer.formatter import TuiFormatter


class Tui(gviewer.BaseDisplayer):
    PALETTE = [
        ("code ok", "light green", "black", "bold"),
        ("code error", "light red", "black", "bold"),
        ("indicator", "yellow", "black", "bold")
    ]
    DEFAULT_EXPORT_REPLAY_FILE = "replay.script"

    def __init__(self, config, stream=None, event_loop=None):
        stream = (
            stream or
            create_msg_channel(config["viewer_channel"], "message")
        )
        data_store = MessageAsyncDataStore(stream.on_recv)

        context = gviewer.DisplayerContext(
            data_store, self, actions=gviewer.Actions([
                ("e", "export replay script", self.export_replay),
                ("r", "replay", self.replay),
                ("L", "log", self.log)]))

        self.log_context = LogDisplayer(config).context
        event_loop = event_loop or urwid.TornadoEventLoop(ioloop.IOLoop.instance())
        self.viewer = gviewer.GViewer(
            context, palette=self.PALETTE,
            other_contexts=[self.log_context],
            config=gviewer.Config(auto_scroll=True),
            event_loop=event_loop)
        self.formatter = TuiFormatter()
        self.config = config
        self.event_client = EventClient(config["events_channel"])
        self.terminal_width, _ = get_terminal_size()

    def start(self):
        if "replay_file" in self.config and self.config["replay_file"]:
            for line in open(self.config["replay_file"], "r"):
                if line:
                    self.execute_replay(json.loads(line))

        self.viewer.start()

    def _code_text_markup(self, code):
        if int(code) < 400:
            return ("code ok", str(code))
        return ("code error", str(code))

    def _fold_path(self, path):
        max_width = self.terminal_width - 16
        return path if len(path) < max_width else path[:max_width - 1] + "..."

    def _format_port(self, scheme, port):
        if (scheme, port) in [("https", 443), ("http", 80)]:
            return ""
        return ":" + str(port)

    def summary(self, message, exported=False):
        mark = "V " if exported else "  "
        pretty_path = self._fold_path("{0}://{1}{2}{3}".format(
            message.scheme,
            message.host,
            self._format_port(message.scheme, message.port),
            message.path)
        )
        return [
            ("indicator", mark),
            self._code_text_markup(message.response.code),
            " {0:7} {1}".format(
                message.request.method,
                pretty_path)
        ]

    def get_views(self):
        return [("Request", self.request_view),
                ("Response", self.response_view),
                ("Detail", self.detail_view)]

    def request_view(self, message):
        groups = []
        request = message.request
        groups.append(gviewer.PropsGroup(
            "",
            [gviewer.Prop("method", request.method),
             gviewer.Prop("path", request.path),
             gviewer.Prop("version", request.version)]))
        groups.append(gviewer.PropsGroup(
            "Request Header",
            [gviewer.Prop(k, v) for k, v in request.headers]))

        if request.body:
            body_list = self.formatter.format_body(
                request.body, request.headers)
            groups.append(gviewer.Group(
                "Request Body", body_list))
        return gviewer.View(groups)

    def response_view(self, message):
        groups = []
        response = message.response
        groups.append(gviewer.PropsGroup(
            "",
            [gviewer.Prop("code", str(response.code)),
             gviewer.Prop("reason", response.reason),
             gviewer.Prop("version", response.version)]))
        groups.append(gviewer.PropsGroup(
            "Response Header",
            [gviewer.Prop(k, v) for k, v in response.headers]))

        if response.body:
            body_list = self.formatter.format_body(
                response.body, response.headers)
            groups.append(gviewer.Group(
                "Response Body", body_list))
        return gviewer.View(groups)

    def detail_view(self, message):
        groups = []

        groups.append(gviewer.PropsGroup(
            "Detail",
            [
                gviewer.Prop("Host", message.host),
                gviewer.Prop("Port", str(message.port)),
                gviewer.Prop("Path", message.path)
            ]
        ))
        if message.client_tls:
            groups.append(gviewer.PropsGroup(
                "Client Connection",
                [
                    gviewer.Prop("TLS Version", message.client_tls.version),
                    gviewer.Prop("Server Name Notation", message.client_tls.sni),
                    gviewer.Prop("Cipher", message.client_tls.cipher),
                    gviewer.Prop("ALPN", message.client_tls.alpn),
                ]
            ))
        if message.server_tls:
            groups.append(gviewer.PropsGroup(
                "Server Connection",
                [
                    gviewer.Prop("TLS Version", message.server_tls.version),
                    gviewer.Prop("Server Name Notation", message.server_tls.sni),
                    gviewer.Prop("Cipher", message.server_tls.cipher),
                    gviewer.Prop("ALPN", message.server_tls.alpn),
                ]
            ))
        return gviewer.View(groups)

    def export_replay(self, parent, message, widget, *args, **kwargs):
        export_file = self.config.get("out_file", self.DEFAULT_EXPORT_REPLAY_FILE)

        with open(export_file, "a") as f:
            f.write(json.dumps(message.serialize()))
            f.write("\n")
        widget.set_title(self.summary(message, exported=True))
        parent.notify("replay script export to {0}".format(export_file))

    def replay(self, parent, message, *args, **kwargs):
        self.event_client.send_event(Event(name=REPLAY, context=message))
        if parent:
            parent.notify("sent replay event to server")

    def execute_replay(self, event):
        self.event_client.send_event(Event(name=REPLAY, context=event))

    def log(self, controller, message, widget, *args, **kwargs):
        controller.open_view_by_context(self.log_context)


class MessageAsyncDataStore(gviewer.AsyncDataStore):  # pragma: no cover
    def transform(self, message):
        context = ViewerContext.deserialize(json.loads(message[1]))
        return context


class LogDisplayer(gviewer.BaseDisplayer):
    def __init__(self, config, stream=None):
        stream = (
            stream or
            create_msg_channel(config["viewer_channel"], "logger")
        )
        data_store = gviewer.AsyncDataStore(stream.on_recv)
        self.context = gviewer.DisplayerContext(
            data_store, self)

    def summary(self, message):
        if "\n" in message[1]:
            return message[1].split("\n")[0]
        else:
            return message[1]

    def get_views(self):
        return [("", self.show)]

    def show(self, message):
        lines = message[1].split("\n")
        lines = map(lambda l: gviewer.Text(l), lines)
        return gviewer.View([gviewer.Group("", lines)])


def create_msg_channel(channel, topic):  # pragma: no cover
    context = zmq.Context()
    socket = context.socket(zmq.SUB)
    socket.connect(channel)
    socket.setsockopt(zmq.SUBSCRIBE, topic)
    return zmqstream.ZMQStream(socket)


def start(config):  # pragma: no cover
    ioloop.install()
    tui = Tui(config)
    tui.start()
