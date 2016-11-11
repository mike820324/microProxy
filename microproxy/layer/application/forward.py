from tornado import concurrent

from microproxy.layer.base import ApplicationLayer


class ForwardLayer(ApplicationLayer):
    '''
    ForwardLayer: passing all the src data to destination. Will not intercept anything
    '''
    def __init__(self, server_state, context):
        super(ForwardLayer, self).__init__(server_state, context)
        self._future = concurrent.Future()

    def process_and_return_context(self):
        self.src_stream.read_until_close(streaming_callback=self.on_request)
        self.src_stream.set_close_callback(self.on_src_close)
        self.dest_stream.read_until_close(streaming_callback=self.on_response)
        self.dest_stream.set_close_callback(self.on_dest_close)
        return self._future

    def on_src_close(self):
        self.dest_stream.close()
        self.on_finish()

    def on_dest_close(self):
        self.src_stream.close()
        self.on_finish()

    def on_finish(self):
        if self._future.running():
            self._future.set_result(self.context)

    def on_request(self, data):
        if not self.dest_stream.closed():
            self.dest_stream.write(data)

    def on_response(self, data):
        if not self.src_stream.closed():
            self.src_stream.write(data)
