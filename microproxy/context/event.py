from base import Serializable


class Event(Serializable):
    def __init__(self, name="", context=None):
        self.name = name
        self.context = context
