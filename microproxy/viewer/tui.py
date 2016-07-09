import zmq
from zmq.eventloop import ioloop, zmqstream
import urwid
import json

import gviewer

ioloop.install()


class Tui(gviewer.BaseDisplayer):
    SUMMARY_MAX_LENGTH = 100
    PALETTE = [
        ("code ok", "light green", "black", "bold"),
        ("code error", "light red", "black", "bold")
    ]

    def __init__(self, stream):
        self.stream = stream
        self.data_store = self.create_data_store()
        self.viewer = gviewer.GViewer(
            self.data_store, self,
            palette=self.PALETTE,
            event_loop=urwid.TornadoEventLoop(ioloop.IOLoop.instance()))

    def create_data_store(self):
        return ZmqAsyncDataStore(self.stream.on_recv)

    def start(self):
        self.viewer.start()

    def _code_text_markup(self, code):
        if int(code) < 400:
            return ("code ok", str(code))
        return ("code error", str(code))

    def _fold_path(self, path):
        return path if len(path) < self.SUMMARY_MAX_LENGTH else path[:self.SUMMARY_MAX_LENGTH - 1] + "..."

    def to_summary(self, message):
        return [
            self._code_text_markup(message["response"]["code"]),
            " {0:5} {1}://{2}{3}".format(
                message["request"]["method"],
                message["scheme"],
                message["host"],
                self._fold_path(message["path"]))]

    def get_detail_displayers(self):
        return [("Detail", HttpDetailDisplayer())]


class ZmqAsyncDataStore(gviewer.AsyncDataStore):
    def transform(self, message):
        return json.loads(message[0])


class HttpDetailDisplayer(gviewer.DetailDisplayer):
    def to_detail_groups(self, message):
        groups = []

        request = message["request"]
        groups.append(gviewer.DetailGroup(
            "Request",
            [gviewer.DetailProp("method", request["method"]),
             gviewer.DetailProp("path", request["path"]),
             gviewer.DetailProp("version", request["version"])]))
        groups.append(gviewer.DetailGroup(
            "Request Header",
            [gviewer.DetailProp(k, v) for k, v in request["headers"]]))

        response = message["response"]
        groups.append(gviewer.DetailGroup(
            "Response",
            [gviewer.DetailProp("code", str(response["code"])),
             gviewer.DetailProp("reason", response["reason"]),
             gviewer.DetailProp("version", response["version"])]))
        groups.append(gviewer.DetailGroup(
            "Response Header",
            [gviewer.DetailProp(k, v) for k, v in response["headers"]]))

        return groups


def create_msg_channel(channel):
    context = zmq.Context()
    socket = context.socket(zmq.SUB)
    socket.connect(channel)
    socket.setsockopt(zmq.SUBSCRIBE, "")
    return socket


def start(config):
    socket = create_msg_channel(config["viewer_channel"])
    stream = zmqstream.ZMQStream(socket)
    tui = Tui(stream)
    tui.start()
