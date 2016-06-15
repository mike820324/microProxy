import sys
import zmq
from zmq.utils import jsonapi as json
from zmq.eventloop import ioloop, zmqstream
import urwid

ioloop.install()


class Message(urwid.WidgetWrap):
    def __init__(self, msg, parent):
        self.msg = json.loads(msg[0])
        self.parent = parent
        super(Message, self).__init__(self._make_widget())

    def _get_title(self):
        host = self.msg["request"]["headers"]["Host"]
        path = self.msg["request"]["path"]
        status_code = self.msg["response"]["code"]
        method = self.msg["request"]["method"]
        return "{0} {1} {2}{3}".format(status_code, method, host, path)

    def _make_widget(self):
        return urwid.AttrMap(urwid.Text(self._get_title()), "message", "message focus")

    def selectable(self):
        return True

    def keypress(self, size, key):
        if key in ("d", "enter"):
            self.parent.open_detail(self.msg)
            return None
        return key


class MessageWalker(urwid.SimpleFocusListWalker):
    def __init__(self, parent):
        super(MessageWalker, self).__init__([])
        self.parent = parent

    def on_msg_recv(self, msg):
        self.append(Message(msg, self.parent))


class MessageList(urwid.ListBox):
    def __init__(self, walker, parent):
        super(MessageList, self).__init__(walker)
        self.walker = walker
        self.parent = parent

    def keypress(self, size, key):
        if key == "k":
            return super(MessageList, self).keypress(size, "up")
        elif key == "j":
            return super(MessageList, self).keypress(size, "down")
        elif key == "ctrl f":
            return super(MessageList, self).keypress(size, "page down")
        elif key == "ctrl b":
            return super(MessageList, self).keypress(size, "page up")
        else:
            return super(MessageList, self).keypress(size, key)


class Detail(urwid.WidgetWrap):
    def __init__(self, message):
        super(Detail, self).__init__(self._make_widget(message))

    def _make_widget(self, message):
        request = message["request"]
        request_list = [PropSeparator("Request"),
                        Prop("method", request["method"]),
                        Prop("path", request["path"]),
                        Prop("version", request["version"]),
                        PropSeparator("Request Header")] + \
                       [Prop(k, v) for k, v in request["headers"].iteritems()]

        response = message["response"]
        response_list = [PropSeparator("Response"),
                         Prop("code", response["code"]),
                         Prop("reason", response["reason"]),
                         Prop("version", response["version"]),
                         PropSeparator("Response Header")] + \
                        [Prop(k, v) for k, v in response["headers"].iteritems()]

        details = request_list + [EmptyLine()] + response_list
        walker = urwid.SimpleFocusListWalker(details)
        return urwid.ListBox(walker)


class Prop(urwid.WidgetWrap):
    def __init__(self, key, value):
        w = urwid.AttrMap(urwid.Text("{0}: {1}".format(key, value)), "prop", "prop focus")
        super(Prop, self).__init__(w)

    def selectable(self):
        return True

    def keypress(self, size, key):
        return key


class PropSeparator(urwid.WidgetWrap):
    def __init__(self, content):
        super(PropSeparator, self).__init__(urwid.AttrMap(urwid.Text(content), "prop separator"))


class EmptyLine(urwid.Text):
    def __init__(self):
        super(EmptyLine, self).__init__("")


class ParentView(urwid.Columns):
    def __init__(self):
        self.walker = MessageWalker(self)
        self.list = MessageList(self.walker, self)
        super(ParentView, self).__init__([self.list])

    def on_msg_recv(self, msg):
        self.walker.on_msg_recv(msg)

    def open_detail(self, message):
        self.remove_view(Detail)
        self.contents.append((Detail(message), self.options()))

    def remove_view(self, clazz):
        for w in self.contents:
            if isinstance(w[0], clazz):
                self.contents.remove(w)

    def keypress(self, size, key):
        if key in ("q", "Q"):
            if len(self.contents) > 1:
                self.contents.pop()
                return None
        return super(ParentView, self).keypress(size, key)


class Tui(object):
    HEADER = "MicroProxy TUI Viewer"
    FOOTER = "q: quit"
    PALETTE = [
        ("header", "white", "dark green", "bold"),
        ("footer", "white", "dark blue", "bold"),
        ("message", "white", "black"),
        ("message focus", "black", "light gray"),
        ("prop", "white", "black"),
        ("prop focus", "black", "light gray"),
        ("prop separator", "white", "dark red", "bold")
    ]

    def __init__(self, stream, io_loop=None):
        self.stream = stream
        self.io_loop = io_loop or ioloop.IOLoop.instance()
        self.loop = None
        self.parent = ParentView()
        header = urwid.AttrMap(urwid.Text(self.HEADER), "header")
        footer = urwid.AttrMap(urwid.Text(self.FOOTER), "footer")
        self.view = urwid.Frame(body=self.parent, header=header, footer=footer)

    def recv_msg(self, msg):
        self.parent.on_msg_recv(msg)

    def start(self):
        self.stream.on_recv(self.recv_msg)
        self.loop = urwid.MainLoop(self.view,
                                   self.PALETTE,
                                   event_loop=urwid.TornadoEventLoop(self.io_loop),
                                   unhandled_input=self.unhandled_input)
        self.loop.run()

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
