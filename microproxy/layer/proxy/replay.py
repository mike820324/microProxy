from tornado import gen

from base import ProxyLayer


class ReplayLayer(ProxyLayer):
    def __init__(self, context):
        super(ReplayLayer, self).__init__(context)

    @gen.coroutine
    def process_and_return_context(self):
        dest_stream = yield self.create_dest_stream(
            (self.context.host, self.context.port))
        self.context.dest_stream = dest_stream

        raise gen.Return(self.context)
