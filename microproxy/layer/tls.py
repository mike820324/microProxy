import ssl

from tornado import gen

from http1 import Http1Layer
from microproxy.utils import get_logger

logger = get_logger(__name__)


class TlsLayer(object):
    def __init__(self, context):
        super(TlsLayer, self).__init__()
        self.context = context

    @gen.coroutine
    def process(self):
        try:
            src_ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            src_ssl_context.load_cert_chain(certfile=self.context.config["certfile"],
                                            keyfile=self.context.config["keyfile"])
            src_stream = yield self.context.src_stream.start_tls(server_side=True, ssl_options=src_ssl_context)

            # Will not verify the server side
            dest_ssl_context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
            dest_ssl_context.check_hostname = False
            dest_ssl_context.verify_mode = ssl.CERT_NONE

            dest_stream = yield self.context.dest_stream.start_tls(server_side=False, ssl_options=dest_ssl_context)
            new_context = self.context.new_context(src_stream=src_stream,
                                                   dest_stream=dest_stream)
            Http1Layer(new_context).process()
        except Exception as e:
            logger.exception(e)
