from copy import copy
from tornado import gen
from tornado import iostream


class NonTlsLayer(object):
    def __init__(self, context):
        super(NonTlsLayer, self).__init__()
        self.context = copy(context)

    @gen.coroutine
    def process(self):
        # we are not going through tls layer
        # chage dest_stream to iostream
        self.context.dest_stream.setblocking(False)
        self.context.dest_stream = iostream.IOStream(self.context.dest_stream)
        self.context.schema = "http"
        raise gen.Return(self.context)
