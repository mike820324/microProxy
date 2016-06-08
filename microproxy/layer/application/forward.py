from tornado import concurrent
from tornado import gen


class ForwardLayer(object):
    '''
    ForwardLayer: passing all the src data to destination. Will not intercept anything
    '''
    def __init__(self, context):
        super(ForwardLayer, self).__init__()
        self.context = context
        self._future = concurrent.Future()

    @gen.coroutine
    def process_and_return_context(self):
        self.context.src_stream.read_until_close(streaming_callback=self.on_request)
        self.context.src_stream.set_close_callback(self.on_src_close)
        self.context.dest_stream.read_until_close(streaming_callback=self.on_response)
        self.context.dest_stream.set_close_callback(self.on_dest_close)
        yield self._future
        raise gen.Return(self.context)

    def on_src_close(self):
        self.context.dest_stream.close()
        if self._future.running():
            self._future.set_result(None)

    def on_dest_close(self):
        self.context.src_stream.close()
        if self._future.running():
            self._future.set_result(None)

    def on_request(self, data):
        if not self.context.dest_stream.closed():
            self.context.dest_stream.write(data)

    def on_response(self, data):
        if not self.context.src_stream.closed():
            self.context.src_stream.write(data)
