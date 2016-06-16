import zmq
from zmq.eventloop import ioloop, zmqstream

import urwid
from widgets import ParentFrame
from style import palette

ioloop.install()


class Tui(object):
    def __init__(self, stream, io_loop=None):
        self.stream = stream
        self.io_loop = io_loop or ioloop.IOLoop.instance()
        self.view = ParentFrame()

    def recv_msg(self, msg):
        self.view.on_msg_recv(msg)

    def start(self):
        self.stream.on_recv(self.recv_msg)
        loop = urwid.MainLoop(
            self.view, palette,
            event_loop=urwid.TornadoEventLoop(self.io_loop),
            unhandled_input=self.unhandled_input)
        loop.run()

    def unhandled_input(self, key):
        if key in ("q", "Q"):
            raise urwid.ExitMainLoop


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
