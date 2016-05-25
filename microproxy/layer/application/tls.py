import ssl
from copy import copy
from tornado import gen
from tornado import concurrent
from tornado.iostream import SSLIOStream

from microproxy.utils import get_logger
logger = get_logger(__name__)


class TlsLayer(object):
    SUPPORT_PROTOCOLS = ["http/1.1"]

    def __init__(self, context):
        super(TlsLayer, self).__init__()
        self.context = context
        self.ssl_sock = None
        self.alpn_info = ""

    def sni_callback(self, ssl_socket, server_hostname, ssl_context):
        try:
            dest_context = self.create_dest_sslcontext()
            self.ssl_sock = dest_context.wrap_socket(self.context.dest_stream,
                                                     server_hostname=server_hostname)

            if ssl.HAS_ALPN:
                self.alpn_info = self.ssl_sock.selected_alpn_protocol()
                if self.alpn_info == 'h2':
                    logger.debug("alpn using h2")
                    ssl_context.set_alpn_protocols(['h2'])
                else:
                    logger.debug("alpn using http/1.1")
                    ssl_context.set_alpn_protocols(['http/1.1'])

        except Exception as e:
            logger.exception(e)
            return ssl.ALERT_DESCRIPTION_HANDSHAKE_FAILURE
        return None

    def create_dest_sslcontext(self):
        dest_ssl_context = ssl.create_default_context()
        if ssl.HAS_ALPN:
            dest_ssl_context.set_alpn_protocols(self.SUPPORT_PROTOCOLS)
        if ssl.HAS_NPN:
            dest_ssl_context.set_npn_protocols(self.SUPPORT_PROTOCOLS)

        return dest_ssl_context

    def create_src_sslcontext(self):
        context = ssl.SSLContext(ssl.PROTOCOL_TLSv1)
        context.load_cert_chain(self.context.config["certfile"],
                                self.context.config["keyfile"])
        context.set_servername_callback(self.sni_callback)

        return context

    @gen.coroutine
    def process(self):
        src_ssl_context = self.create_src_sslcontext()
        src_stream = yield self.context.src_stream.start_tls(server_side=True,
                                                             ssl_options=src_ssl_context)
        self.ssl_sock.setblocking(False)
        dest_stream = SSLIOStream(self.ssl_sock)

        new_context = copy(self.context)
        new_context.src_stream = src_stream
        new_context.dest_stream = dest_stream

        if self.alpn_info == "http/1.1":
            new_context.schema = "https"
        elif self.alpn_info == "h2":
            new_context.schema = "h2"
        else:
            new_context.schema = "https"

        process_result = self.context.layer_manager.next_layer(self, new_context).process()
        if isinstance(process_result, concurrent.Future):
            yield process_result
        raise gen.Return(None)
