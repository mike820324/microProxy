import zmq
import json
from colored import fg, bg, attr


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
    TITLE = "Request Headers:"
    FG_COLOR = "blue"
    ATTRS = ["bold"]

    def __init__(self, headers):
        super(Request, self).__init__(
            [ColorText(self.TITLE, fg_color=self.FG_COLOR, attrs=self.ATTRS),
             Header(headers)])

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.__dict__ == other.__dict__
        else:
            return False

    def __neq__(self, other):
        return not self.__eq__(other)


class Response(TextList):
    TITLE = "Response Headers:"
    FG_COLOR = "blue"
    ATTRS = ["bold"]

    def __init__(self, headers):
        super(Response, self).__init__(
            [ColorText(self.TITLE, fg_color=self.FG_COLOR, attrs=self.ATTRS),
             Header(headers)])

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.__dict__ == other.__dict__
        else:
            return False

    def __neq__(self, other):
        return not self.__eq__(other)


def construct_status_summary(request, response):
    # TODO: need update here when we implement new context system
    host = "<host unimplement>"
    path = request["path"]
    status_code = response["code"]
    method = request["method"]
    return StatusText(status_code, method, host, path)


def construct_color_msg(message, verbose_level):
    request = message["request"]
    response = message["response"]
    status = construct_status_summary(request, response)

    if verbose_level == "status":
        return status
    if verbose_level == "header":
        return TextList([status, Request(request["headers"]), Response(response["headers"])])
    elif verbose_level == "body":
        raise NotImplementedError
    elif verbose_level == "all":
        raise NotImplementedError


def create_msg_channel(channel):
    context = zmq.Context()
    socket = context.socket(zmq.SUB)
    socket.connect(channel)
    socket.setsockopt(zmq.SUBSCRIBE, "")
    return socket


def start(config):
    socket = create_msg_channel(config["viewer_channel"])
    verbose_level = config["verbose_level"]
    print ColorText("MicroProxy Simple Viewer v0.0.2",
                    fg_color="blue",
                    attrs=["bold"])
    while True:
        try:
            data = socket.recv()
            message = json.loads(data)
            print construct_color_msg(message, verbose_level)
            print
        except KeyboardInterrupt:
            print ColorText("Closing Simple Viewer",
                            fg_color="blue",
                            attrs=["bold"])
            exit(0)
