from tornado import gen

from microproxy.protocol import tls
from base import ProxyLayer


class ReplayLayer(ProxyLayer):
    def __init__(self, context):
        super(ReplayLayer, self).__init__(context)

    @gen.coroutine
    def process_and_return_context(self):
        dest_stream = yield self.create_dest_stream(
            (self.context.host, self.context.port))

        if self.context.scheme in ("https", "h2"):
            if self.context.scheme == "h2":
                alpn = ["h2"]
            else:
                alpn = None
            dest_stream = yield dest_stream.start_tls(
                server_side=False, ssl_options=tls.create_dest_sslcontext(alpn))

        self.context.dest_stream = dest_stream
        raise gen.Return(self.context)
