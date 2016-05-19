import ssl
from tornado import gen

from microproxy.utils import get_logger
logger = get_logger(__name__)


class TlsLayer(object):
    def __init__(self, context):
        super(TlsLayer, self).__init__()
        self.context = context

    @gen.coroutine
    def process(self):
        try:
            server_ssl_options = dict(certfile=self.context.config["certfile"],
                                      keyfile=self.context.config["keyfile"],)
            src_stream = yield self.context.src_stream.start_tls(server_side=True,
                                                                 ssl_options=server_ssl_options)

            dest_stream = yield self.context.dest_stream.start_tls(server_side=False,
                                                                   ssl_options=dict(cert_reqs=ssl.CERT_NONE))
            new_context = self.context.new_context(src_stream=src_stream,
                                                   dest_stream=dest_stream)
            self.context.layer_manager.next_layer(self, new_context).process()
        except Exception as e:
            logger.exception(e)
