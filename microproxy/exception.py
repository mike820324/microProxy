from tornado import iostream


class ProtocolError(Exception):
    pass


class SrcStreamClosedError(iostream.StreamClosedError):
    pass


class DestNotConnectedError(iostream.StreamClosedError):
    pass


class DestStreamClosedError(iostream.StreamClosedError):
    pass


class Http2Error(Exception):
    def __init__(self, conn, error, error_msg, stream_id=None):
        if stream_id:
            err = "{0}: {1} on {2}, stream_id={3}, cause is {4}".format(
                type(error), error_msg, conn, stream_id, error.args)
        else:
            err = "{0}: {1} on {2}, cause is {3}".format(
                type(error), error_msg, conn, error.args)
        super(Http2Error, self).__init__(err)
