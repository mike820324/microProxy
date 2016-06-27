import urwid
from zmq.utils import jsonapi as json


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
        return "{0} {1:5} {2}{3}".format(status_code, method, host, path)

    def _make_widget(self):
        return urwid.AttrMap(
            urwid.Text(self._get_title()), "message", "message focus")

    def selectable(self):
        return True

    def keypress(self, size, key):
        if key in ("d", "enter"):
            self.parent.open_detail(self.msg)
            return None
        return key
