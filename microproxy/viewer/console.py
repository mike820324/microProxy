from microproxy.version import VERSION
import zmq
import json
from colored import fg, bg, attr

from microproxy.event import EventClient
from format import Formatter

_formatter = Formatter()


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

    def __str__(self):
        if not (self.fg_color or self.bg_color or self.attrs):
            return self.text
        _str = fg(self.fg_color) if self.fg_color else ""
        _str += bg(self.bg_color) if self.bg_color else ""
        _str += "".join(map(lambda a: attr(a), self.attrs))
        _str += self.text
        _str += attr("reset")
        return _str

    def __repr__(self):
        return self.__str__()

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.__dict__ == other.__dict__
        else:
            return False

    def __neq__(self, other):
        return not self.__eq__(other)


class TextList(object):
    def __init__(self, text_list, delimiter="\n"):
        self.text_list = text_list
        self.delimiter = delimiter

    def __str__(self):
        return self.delimiter.join(map(lambda s: str(s), self.text_list))

    def __repr__(self):
        return self.__str__()

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.__dict__ == other.__dict__
        else:
            return False

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
            delimiter=" ")

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.__dict__ == other.__dict__
        else:
            return False

    def __neq__(self, other):
        return not self.__eq__(other)


class Header(TextList):
    BG_COLOR = "blue"

    def __init__(self, headers):
        super(Header, self).__init__(
            map(lambda (k, v): ColorText("{0}: {1}".format(k, v),
                bg_color=self.BG_COLOR), headers))

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.__dict__ == other.__dict__
        else:
            return False

    def __neq__(self, other):
        return not self.__eq__(other)


class Request(TextList):
    HEADER_TITLE = "Request Headers:"
    BODY_TITLE = "Request Body:"
    FG_COLOR = "blue"
    ATTRS = ["bold"]

    def __init__(self, request, show_body=False):
        content = []
        content.append(ColorText(self.HEADER_TITLE, fg_color=self.FG_COLOR, attrs=self.ATTRS))
        content.append(Header(request["headers"]))
        if show_body and request["body"]:
            content.append(ColorText(self.BODY_TITLE, fg_color=self.FG_COLOR, attrs=self.ATTRS))
            content = content + _formatter.format_request(request)
        super(Request, self).__init__(content)

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.__dict__ == other.__dict__
        else:
            return False

    def __neq__(self, other):
        return not self.__eq__(other)


class Response(TextList):
    HEADER_TITLE = "Response Headers:"
    BODY_TITLE = "Response Body:"
    FG_COLOR = "blue"
    ATTRS = ["bold"]

    def __init__(self, response, show_body=False):
        content = []
        content.append(ColorText(self.HEADER_TITLE, fg_color=self.FG_COLOR, attrs=self.ATTRS))
        content.append(Header(response["headers"]))
        if show_body and response["body"]:
            content.append(ColorText(self.BODY_TITLE, fg_color=self.FG_COLOR, attrs=self.ATTRS))
            content = content + _formatter.format_request(response)
        super(Response, self).__init__(content)

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.__dict__ == other.__dict__
        else:
            return False

    def __neq__(self, other):
        return not self.__eq__(other)


def construct_status_summary(message):
    # TODO: need update here when we implement new context system
    host = message["host"]
    path = message["path"]
    status_code = message["response"]["code"]
    method = message["request"]["method"]
    return StatusText(status_code, method, host, path)


def construct_color_msg(message, verbose_level):
    status = construct_status_summary(message)
    request = message["request"]
    response = message["response"]

    if verbose_level == "status":
        return status
    if verbose_level == "header":
        return TextList([status, Request(request), Response(response)])
    elif verbose_level == "body":
        return TextList([status, Request(request, show_body=True), Response(response, show_body=True)])
    elif verbose_level == "all":
        return TextList([status, Request(request, show_body=True), Response(response, show_body=True)])


def create_msg_channel(channel):
    context = zmq.Context()
    socket = context.socket(zmq.SUB)
    socket.connect(channel)
    socket.setsockopt(zmq.SUBSCRIBE, "")
    return socket


def replay(channel_addr, replay_file):
    client = EventClient(channel_addr)
    for line in open(replay_file, "r"):
        if line:
            client.send_event(json.loads(line))


def start(config):
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
            data = socket.recv()
            message = json.loads(data)
            if dump_file:
                fp.write(data)
                fp.write("\n")

            print construct_color_msg(message, verbose_level)
            print
        except KeyboardInterrupt:
            print ColorText("Closing Simple Viewer",
                            fg_color="blue",
                            attrs=["bold"])
            if dump_file:
                fp.close()
            exit(0)
