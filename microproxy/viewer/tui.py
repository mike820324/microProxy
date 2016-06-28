import zmq
from zmq.eventloop import ioloop, zmqstream
import urwid
import json

import gviewer

ioloop.install()


class Tui(gviewer.BaseDisplayer):
    SUMMARY_MAX_LENGTH = 100

    def __init__(self, stream):
        self.stream = stream
        self.data_store = self.create_data_store()
        self.viewer = gviewer.GViewer(
            self.data_store, self, event_loop=urwid.TornadoEventLoop(ioloop.IOLoop.instance()))

    def create_data_store(self):
        return gviewer.AsyncDataStore(self.stream.on_recv)

    def start(self):
        self.viewer.start()

    def to_summary(self, message):
        msg_dict = json.loads(message[0])
        summary = "{0} {1:5} {2}{3}".format(
            msg_dict["response"]["code"],
            msg_dict["request"]["method"],
            msg_dict["request"]["headers"]["Host"],
            msg_dict["request"]["path"])
        return summary[:self.SUMMARY_MAX_LENGTH] + ".." \
            if len(summary) > self.SUMMARY_MAX_LENGTH else summary

    def to_detail_groups(self, message):
        msg_dict = json.loads(message[0])
        groups = []

        request = msg_dict["request"]
        groups.append(gviewer.DetailGroup(
            "Request",
            [gviewer.DetailProp("method", request["method"]),
             gviewer.DetailProp("path", request["path"]),
             gviewer.DetailProp("version", request["version"])]))
        groups.append(gviewer.DetailGroup(
            "Request Header",
            [gviewer.DetailProp(k, v) for k, v in request["headers"].iteritems()]))

        response = msg_dict["response"]
        groups.append(gviewer.DetailGroup(
            "Response",
            [gviewer.DetailProp("code", response["code"]),
             gviewer.DetailProp("reason", response["reason"]),
             gviewer.DetailProp("version", response["version"])]))
        groups.append(gviewer.DetailGroup(
            "Response Header",
            [gviewer.DetailProp(k, v) for k, v in response["headers"].iteritems()]))

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
