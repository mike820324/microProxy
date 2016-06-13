from OpenSSL import SSL
from copy import copy
from tornado import gen, concurrent

from microproxy.iostream import MicroProxySSLIOStream
from microproxy.utils import get_logger
logger = get_logger(__name__)


class TlsLayer(object):
    SUPPORT_PROTOCOLS = ["http/1.1"]

    def __init__(self, context):
        super(TlsLayer, self).__init__()
        self.context = copy(context)
        # tuple contains (dest_ssl_sock, hostname, alpn_info) or exception if failed
        self._alpn_future = concurrent.Future()

    def src_alpn_callback(self, src_ssl_conn, src_alpn):
        try:
            support_alpn = [
                protocol
                for protocol in src_alpn
                if protocol in self.SUPPORT_PROTOCOLS
            ]

            dest_context = self.create_dest_sslcontext(support_alpn)
            ssl_sock = SSL.Connection(dest_context,
                                      self.context.dest_stream)

            hostname = src_ssl_conn.get_servername()

            if hostname:
                ssl_sock.set_tlsext_host_name(hostname)

            ssl_sock.set_connect_state()
            ssl_sock.do_handshake()

            alpn_info = ssl_sock.get_alpn_proto_negotiated() or b"http/1.1"

            logger.debug("Choose {0} as application protocol".format(alpn_info))
            self._alpn_future.set_result((ssl_sock,
                                          hostname,
                                          alpn_info))
            return bytes(alpn_info)
        except Exception as e:
            # According to the document on PyOpenSSL
            # It said that the callback function should return a bytestring that determine the alpn protocol
            # We could not know what will happen if we throw exception here
            # So I think we log the exception here and handle the problem in another place
            self._alpn_future.set_result(e)
            return None

    def create_dest_sslcontext(self, alpn):
        ssl_ctx = SSL.Context(SSL.TLSv1_METHOD)
        ssl_ctx.set_options(SSL.OP_NO_SSLv2)
        ssl_ctx.set_verify(SSL.VERIFY_NONE,
                           lambda conn, x509, err_num, err_depth, err_code: True)
        ssl_ctx.set_alpn_protos(alpn)

        return ssl_ctx

    def create_src_sslcontext(self):
        ssl_ctx = SSL.Context(SSL.TLSv1_METHOD)
        ssl_ctx.set_options(SSL.OP_NO_SSLv2)
        ssl_ctx.use_certificate_file(self.context.config["certfile"])
        ssl_ctx.use_privatekey_file(self.context.config["keyfile"])
        ssl_ctx.set_alpn_select_callback(self.src_alpn_callback)

        return ssl_ctx

    @gen.coroutine
    def process_and_return_context(self):
        self.context.src_stream.resume()
        src_ssl_ctx = self.create_src_sslcontext()
        src_stream = yield self.context.src_stream.start_tls(server_side=True,
                                                             ssl_options=src_ssl_ctx)

        dest_ssl_sock, hostname, alpn_info = yield self._alpn_future
        dest_ssl_sock.setblocking(False)
        dest_stream = MicroProxySSLIOStream(dest_ssl_sock)
        self.context.src_stream = src_stream
        self.context.dest_stream = dest_stream

        if hostname:
            self.context.host = hostname
        if alpn_info == "http/1.1":
            self.context.scheme = "https"
        elif alpn_info == "h2":
            self.context.scheme = "h2"
        else:
            self.context.scheme = "https"

        raise gen.Return(self.context)
