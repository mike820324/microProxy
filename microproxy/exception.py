from tornado import iostream


class ProtocolError(Exception):
    pass


class SrcStreamClosedError(iostream.StreamClosedError):
    pass


class DestStreamClosedError(iostream.StreamClosedError):
    pass
