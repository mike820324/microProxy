import ssl
from copy import copy
from tornado import gen
from tornado import concurrent

from microproxy.utils import get_logger
logger = get_logger(__name__)


class TlsLayer(object):
    def __init__(self, context):
        super(TlsLayer, self).__init__()
        self.context = context

    @gen.coroutine
    def process(self):
        server_ssl_options = dict(certfile=self.context.config["certfile"],
                                  keyfile=self.context.config["keyfile"],)
        src_stream = yield self.context.src_stream.start_tls(server_side=True,
                                                             ssl_options=server_ssl_options)

        dest_stream = yield self.context.dest_stream.start_tls(server_side=False,
                                                               ssl_options=dict(cert_reqs=ssl.CERT_NONE),
                                                               server_hostname=self.context.host)

        new_context = copy(self.context)
        new_context.src_stream = src_stream
        new_context.dest_stream = dest_stream
        process_result = self.context.layer_manager.next_layer(self, new_context).process()
        if isinstance(process_result, concurrent.Future):
            yield process_result
        raise gen.Return(None)
