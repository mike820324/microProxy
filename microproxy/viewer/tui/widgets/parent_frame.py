import urwid
from message_list import MessageList, MessageWalker
from detail_view import Detail


class ParentFrame(urwid.Frame):
    HEADER = "MicroProxy TUI Viewer"
    FOOTER = "q: quit"

    def __init__(self):
        header = urwid.AttrMap(urwid.Text(self.HEADER), "header")
        footer = urwid.AttrMap(urwid.Text(self.FOOTER), "footer")
        self.walker = MessageWalker(self)
        self.list = MessageList(self.walker, self)
        super(ParentFrame, self).__init__(
            body=self.list, header=header, footer=footer)

    def on_msg_recv(self, msg):
        self.walker.on_msg_recv(msg)

    def open_detail(self, message):
        self.set_body(Detail(message))

    def close_detail(self):
        self.set_body(self.list)

    def keypress(self, size, key):
        if key in ("q", "Q"):
            if isinstance(self.get_body(), Detail):
                self.close_detail()
                return None
        return super(ParentFrame, self).keypress(size, key)
