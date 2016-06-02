from OpenSSL import SSL
from copy import copy
from tornado import gen

from microproxy.iostream import MicroProxySSLIOStream
from microproxy.utils import get_logger
logger = get_logger(__name__)


class TlsLayer(object):
    SUPPORT_PROTOCOLS = ["http/1.1"]

    def __init__(self, context):
        super(TlsLayer, self).__init__()
        self.context = copy(context)
        self.ssl_sock = None

    def src_alpn_callback(self, src_ssl_conn, alpn):
        try:
            dest_context = self.create_dest_sslcontext(alpn)
            self.ssl_sock = SSL.Connection(dest_context,
                                           self.context.dest_stream)
            self.ssl_sock.set_tlsext_host_name(self.context.host)
            self.ssl_sock.set_connect_state()
            self.ssl_sock.do_handshake()

            alpn_info = self.ssl_sock.get_alpn_proto_negotiated()

            if alpn_info == "http/1.1":
                self.context.schema = "https"
            elif alpn_info == "h2":
                self.context.schema = "h2"
            else:
                self.context.schema = "https"
            return bytes(alpn_info)

        except Exception as e:
            logger.exception(e)
            raise
        return None

    def src_sni_callback(self, src_ssl_conn):
        self.context.host = src_ssl_conn.get_servername()

    def create_dest_sslcontext(self, alpn):
        dest_ssl_context = SSL.Context(SSL.SSLv23_METHOD)
        dest_ssl_context.set_alpn_protos(alpn)

        return dest_ssl_context

    def create_src_sslcontext(self):
        context = SSL.Context(SSL.SSLv23_METHOD)
        context.use_certificate_file(self.context.config["certfile"])
        context.use_privatekey_file(self.context.config["keyfile"])
        context.set_tlsext_servername_callback(self.src_sni_callback)
        context.set_alpn_select_callback(self.src_alpn_callback)

        return context

    @gen.coroutine
    def process(self):
        src_ssl_context = self.create_src_sslcontext()
        try:
            src_stream = yield self.context.src_stream.start_tls(server_side=True,
                                                                 ssl_options=src_ssl_context)
        except Exception as e:
            logger.exception(e)
            raise

        self.ssl_sock.setblocking(False)
        dest_stream = MicroProxySSLIOStream(self.ssl_sock)

        self.context.src_stream = src_stream
        self.context.dest_stream = dest_stream

        raise gen.Return(self.context)
