class ProtocolError(Exception):
    pass


class StreamClosedError(Exception):
    def __init__(self, layer, detail="closed"):
        super(StreamClosedError, self).__init__(
            "Stream is closed on {0}: {1}".format(type(layer).__name__, detail))


class SrcStreamClosedError(StreamClosedError):
    pass


class DestStreamClosedError(StreamClosedError):
    pass


class DestNotConnectedError(Exception):
    def __init__(self, addr):
        super(DestNotConnectedError, self).__init__(
            "Address: {0}".format(addr))


class Http2Error(Exception):
    def __init__(self, conn, error, error_msg, stream_id=None):
        if stream_id:
            err = "{0}: {1} on {2}, stream_id={3}, cause is {4}".format(
                type(error), error_msg, conn, stream_id, error.args)
        else:
            err = "{0}: {1} on {2}, cause is {3}".format(
                type(error), error_msg, conn, error.args)
        super(Http2Error, self).__init__(err)


class TlsError(Exception):
    pass
