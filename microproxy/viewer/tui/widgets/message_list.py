import urwid
from message import Message


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
