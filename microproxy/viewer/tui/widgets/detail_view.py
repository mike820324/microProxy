import urwid


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
        w = urwid.AttrMap(
            urwid.Text("{0}: {1}".format(key, value)), "prop", "prop focus")
        super(Prop, self).__init__(w)

    def selectable(self):
        return True

    def keypress(self, size, key):
        return key


class PropSeparator(urwid.WidgetWrap):
    def __init__(self, content):
        super(PropSeparator, self).__init__(
            urwid.AttrMap(urwid.Text(content), "prop separator"))


class EmptyLine(urwid.Text):
    def __init__(self):
        super(EmptyLine, self).__init__("")
