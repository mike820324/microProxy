from microproxy.version import VERSION
import zmq
import json
from colored import fg, bg, attr

from microproxy.context import ViewerContext, Event
from microproxy.event import EventClient, REPLAY
from formatter import ConsoleFormatter

_formatter = ConsoleFormatter()


class ColorText(object):
    def __init__(self,
                 text,
                 fg_color=None,
                 bg_color=None,
                 attrs=None):
        self.text = str(text)
        self.fg_color = fg_color
        self.bg_color = bg_color
        self.attrs = attrs or []

    def __unicode__(self):
        if not (self.fg_color or self.bg_color or self.attrs):
            return self.text.decode("utf8")
        _str = fg(self.fg_color).decode("utf8") if self.fg_color else u""
        _str += bg(self.bg_color).decode("utf8") if self.bg_color else u""
        _str += u"".join(map(lambda a: attr(a), self.attrs))
        _str += self.text.decode("utf8")
        _str += attr("reset").decode("utf8")
        return _str

    def __str__(self):
        return self.__unicode__().encode("utf8")

    def __repr__(self):
        return self.__str__()

    def __eq__(self, other):
        return (
            type(self) is type(other) and
            self.__dict__ == other.__dict__
        )

    def __neq__(self, other):
        return not self.__eq__(other)


class TextList(object):
    def __init__(self, text_list, delimiter=u"\n"):
        self.text_list = text_list
        self.delimiter = delimiter

    def __unicode__(self):
        return self.delimiter.join(map(lambda s: unicode(s), self.text_list))

    def __str__(self):
        return self.__unicode__().encode("utf8")

    def __repr__(self):
        return self.__str__()

    def __eq__(self, other):
        return (
            type(self) is type(other) and
            self.__dict__ == other.__dict__
        )

    def __neq__(self, other):
        return not self.__eq__(other)


class StatusText(TextList):
    FG_COLOR_OK = "green"
    FG_COLOR_NOT_OK = "red"
    ATTRS = ["bold"]

    def __init__(self, status_code, method, host, path):
        status_fg = self.FG_COLOR_OK if status_code < 400 else self.FG_COLOR_NOT_OK
        super(StatusText, self).__init__(
            [ColorText(status_code, fg_color=status_fg, attrs=self.ATTRS),
             method,
             host + path],
            delimiter=u" ")


class Header(TextList):
    BG_COLOR = "blue"

    def __init__(self, headers):
        super(Header, self).__init__(
            map(lambda (k, v): ColorText("{0}: {1}".format(k, v),
                bg_color=self.BG_COLOR), headers))


class Request(TextList):
    HEADER_TITLE = "Request Headers:"
    BODY_TITLE = "Request Body:"
    FG_COLOR = "blue"
    ATTRS = ["bold"]

    def __init__(self, request, show_body=False):
        content = []
        content.append(ColorText(self.HEADER_TITLE, fg_color=self.FG_COLOR, attrs=self.ATTRS))
        content.append(Header(request.headers))
        if show_body and request.body:
            content.append(ColorText(self.BODY_TITLE, fg_color=self.FG_COLOR, attrs=self.ATTRS))
            body = _formatter.format_body(request.body, request.headers)
            content.append(body)
        super(Request, self).__init__(content)


class Response(TextList):
    HEADER_TITLE = "Response Headers:"
    BODY_TITLE = "Response Body:"
    FG_COLOR = "blue"
    ATTRS = ["bold"]

    def __init__(self, response, show_body=False):
        content = []
        content.append(ColorText(self.HEADER_TITLE, fg_color=self.FG_COLOR, attrs=self.ATTRS))
        content.append(Header(response.headers))
        if show_body and response.body:
            content.append(ColorText(self.BODY_TITLE, fg_color=self.FG_COLOR, attrs=self.ATTRS))
            body = _formatter.format_body(response.body, response.headers)
            content.append(body)
        super(Response, self).__init__(content)


def construct_status_summary(message):
    # TODO: need update here when we implement new context system
    host = message.host
    path = message.path
    status_code = message.response.code
    method = message.request.method
    return StatusText(status_code, method, host, path)


def construct_color_msg(message, verbose_level):
    status = construct_status_summary(message)

    if verbose_level == "status":
        return status
    if verbose_level == "header":
        return TextList([status, Request(message.request), Response(message.response)])
    elif verbose_level in ("body", "all"):
        return TextList([
            status, Request(message.request, show_body=True),
            Response(message.response, show_body=True)])


def create_msg_channel(channel):  # pragma: no cover
    context = zmq.Context()
    socket = context.socket(zmq.SUB)
    socket.connect(channel)
    socket.setsockopt(zmq.SUBSCRIBE, "message")
    return socket


def replay(channel_addr, replay_file):  # pragma: no cover
    client = EventClient(channel_addr)
    for line in open(replay_file, "r"):
        if line:
            ctx = json.loads(line)
            event = Event(REPLAY, ctx)
            client.send_event(event)


def start(config):  # pragma: no cover
    proxy_host = config["proxy_host"]
    viewer_channel = "{0}:{1}".format(proxy_host, config["viewer_port"])
    events_channel = "{0}:{1}".format(proxy_host, config["events_port"])
    socket = create_msg_channel(viewer_channel)
    verbose_level = config["verbose_level"]
    print ColorText("MicroProxy Simple Viewer {}".format(VERSION),
                    fg_color="blue",
                    attrs=["bold"])

    if "replay_file" in config and config["replay_file"]:
        replay(events_channel, config["replay_file"])

    dump_file = None
    if "dump_file" in config and config["dump_file"]:
        dump_file = config["dump_file"]

    if dump_file:
        fp = open(dump_file, "w")

    while True:
        try:
            topic, data = socket.recv_multipart()
            viewer_context = ViewerContext.deserialize(json.loads(data))
            if dump_file:
                fp.write(data)
                fp.write("\n")

            print construct_color_msg(viewer_context, verbose_level)
            print
        except KeyboardInterrupt:
            print ColorText("Closing Simple Viewer",
                            fg_color="blue",
                            attrs=["bold"])
            if dump_file:
                fp.close()
            exit(0)
