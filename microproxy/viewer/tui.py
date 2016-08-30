import zmq
from zmq.eventloop import ioloop, zmqstream
import urwid
import json

import gviewer
from microproxy.event import EventClient
from format import Formatter

ioloop.install()


class Tui(gviewer.BaseDisplayer):
    SUMMARY_MAX_LENGTH = 100
    PALETTE = [
        ("code ok", "light green", "black", "bold"),
        ("code error", "light red", "black", "bold")
    ]
    DEFAULT_EXPORT_REPLAY_FILE = "replay.script"

    def __init__(self, stream, config):
        self.stream = stream
        self.data_store = self.create_data_store()
        self.viewer = gviewer.GViewer(
            self.data_store, self,
            summary_actions=dict(e=self.export_replay,
                                 r=self.replay),
            palette=self.PALETTE,
            event_loop=urwid.TornadoEventLoop(ioloop.IOLoop.instance()))
        self.formatter = Formatter()
        self.config = config
        self.event_client = EventClient(config["events_channel"])

    def create_data_store(self):
        return ZmqAsyncDataStore(self.stream.on_recv)

    def start(self):
        if "replay_file" in self.config and self.config["replay_file"]:
            for line in open(self.config["replay_file"], "r"):
                if line:
                    self.replay(None, json.loads(line))

        self.viewer.start()

    def _code_text_markup(self, code):
        if int(code) < 400:
            return ("code ok", str(code))
        return ("code error", str(code))

    def _fold_path(self, path):
        return path if len(path) < self.SUMMARY_MAX_LENGTH else path[:self.SUMMARY_MAX_LENGTH - 1] + "..."

    def summary(self, message):
        return [
            self._code_text_markup(message["response"]["code"]),
            " {0:7} {1}://{2}{3}".format(
                message["request"]["method"],
                message["scheme"],
                message["host"],
                self._fold_path(message["path"]))]

    def get_views(self):
        return [("Request", self.request_view),
                ("Response", self.response_view)]

    def request_view(self, message):
        groups = []
        request = message["request"]
        groups.append(gviewer.PropsGroup(
            "",
            [gviewer.Prop("method", request["method"]),
             gviewer.Prop("path", request["path"]),
             gviewer.Prop("version", request["version"])]))
        groups.append(gviewer.PropsGroup(
            "Request Header",
            [gviewer.Prop(k, v) for k, v in request["headers"]]))

        if request["body"]:
            groups.append(gviewer.Group(
                "Request Body",
                [gviewer.Line(s) for s in self.formatter.format_request(request)]))
        return gviewer.View(groups)

    def response_view(self, message):
        groups = []
        response = message["response"]
        groups.append(gviewer.PropsGroup(
            "",
            [gviewer.Prop("code", str(response["code"])),
             gviewer.Prop("reason", response["reason"]),
             gviewer.Prop("version", response["version"])]))
        groups.append(gviewer.PropsGroup(
            "Response Header",
            [gviewer.Prop(k, v) for k, v in response["headers"]]))

        if response["body"]:
            groups.append(gviewer.Group(
                "Response Body",
                [gviewer.Line(s) for s in self.formatter.format_response(response)]))
        return gviewer.View(groups)

    def export_replay(self, parent, message):
        if "out_file" in self.config:
            export_file = self.config["out_file"]
        else:
            export_file = self.DEFAULT_EXPORT_REPLAY_FILE

        with open(export_file, "a") as f:
            f.write(json.dumps(message))
            f.write("\n")
        parent.notify("replay script export to {0}".format(export_file))

    def replay(self, parent, message):
        self.event_client.send_event(message)
        parent.notify("sent replay event to server")


class ZmqAsyncDataStore(gviewer.AsyncDataStore):
    def transform(self, message):
        return json.loads(message[0])


def create_msg_channel(channel):
    context = zmq.Context()
    socket = context.socket(zmq.SUB)
    socket.connect(channel)
    socket.setsockopt(zmq.SUBSCRIBE, "")
    return socket


def start(config):
    socket = create_msg_channel(config["viewer_channel"])
    stream = zmqstream.ZMQStream(socket)
    tui = Tui(stream, config)
    tui.start()
