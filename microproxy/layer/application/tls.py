from OpenSSL import SSL, crypto
from copy import copy
from tornado import gen, concurrent
import time

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

    def create_cert(self, common_name):
        # FIXME: Should add Server Alternative Name extensions.
        # FIXME: Should be able to reuse certificate.

        root_ca_file = self.context.config["certfile"]
        with open(root_ca_file, "rb") as fp:
            _buffer = fp.read()
        ca_root = crypto.load_certificate(crypto.FILETYPE_PEM, _buffer)

        private_key_file = self.context.config["keyfile"]
        with open(private_key_file, "rb") as fp:
            _buffer = fp.read()
        private_key = crypto.load_privatekey(crypto.FILETYPE_PEM, _buffer)

        cert = crypto.X509()

        # NOTE: Expire time 3 yr
        cert.gmtime_adj_notBefore(-3600 * 48)
        cert.gmtime_adj_notAfter(94608000)
        cert.get_subject().CN = common_name
        cert.set_serial_number(int(time.time()) * 10000)

        cert.set_issuer(ca_root.get_subject())
        cert.set_pubkey(ca_root.get_pubkey())
        cert.set_version(2)
        logger.debug("{0}:{1} -> Signing {2}".format(self.context.host,
                                                     self.context.port,
                                                     common_name))
        cert.sign(private_key, "sha256")

        return (cert, private_key)

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

            # NOTE: If the sni hostname is not the same as self.context.host,
            # we use sni hostname instead. Since it's more reliable.
            if hostname and hostname != self.context.host:
                cert, priv_key = self.create_cert(hostname)
                ssl_ctx = SSL.Context(SSL.TLSv1_METHOD)
                ssl_ctx.set_options(SSL.OP_NO_SSLv2)
                ssl_ctx.use_certificate(cert)
                ssl_ctx.use_privatekey(priv_key)
                src_ssl_conn.set_context(ssl_ctx)

            ssl_sock.set_connect_state()
            ssl_sock.do_handshake()

            alpn_info = ssl_sock.get_alpn_proto_negotiated() or b"http/1.1"

            logger.debug("{0}:{1} -> Choose {2} as application protocol".format(self.context.host,
                                                                                self.context.port,
                                                                                alpn_info))
            self._alpn_future.set_result((ssl_sock,
                                          hostname,
                                          alpn_info))
            return bytes(alpn_info)
        except Exception as e:
            # According to the document on PyOpenSSL
            # It said that the callback function should return a bytestring that determine the alpn protocol
            # We could not know what will happen if we throw exception here
            # So I think we log the exception here and handle the problem in another place
            logger.error("{0}:{1} -> ".format(self.context.host,
                                              self.context.port))
            logger.exception(e)
            self._alpn_future.set_result(e)
            return bytes("")

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

        # FIXME: Should be avaliable to remove this part.
        # Currently, If we remove this part,
        # the whole tls negotiation will failed.
        cert, priv_key = self.create_cert(self.context.host)
        ssl_ctx.use_certificate(cert)
        ssl_ctx.use_privatekey(priv_key)

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
