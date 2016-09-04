from copy import copy
from OpenSSL import SSL
from service_identity import VerificationError
from service_identity.pyopenssl import verify_hostname
from tornado import gen, concurrent
from tornado.iostream import StreamClosedError

from microproxy.iostream import MicroProxySSLIOStream
from microproxy.utils import get_logger
from microproxy.protocol import tls
from microproxy.cert import get_cert_store
from microproxy.exception import SrcStreamClosedError
logger = get_logger(__name__)


class TlsLayer(object):
    SUPPORT_PROTOCOLS = ("http/1.1", "h2")

    def __init__(self, context):
        super(TlsLayer, self).__init__()
        self.context = copy(context)
        self.config = self.context.config
        self.cert_store = get_cert_store()
        # NOTE: tuple contains (dest_ssl_sock, hostname, alpn_info)
        # Throws exception if failed
        self._alpn_future = concurrent.Future()
        self._server_hostname = None

    def connect_dest(self, support_alpn, hostname):
        dest_context = tls.create_dest_sslcontext(
            insecure=(self.config["insecure"] == "yes"),
            trusted_ca_certs=self.config["client_certs"],
            alpn=support_alpn)

        dest_sock = self.context.dest_stream.detach()
        dest_sock.setblocking(True)

        ssl_sock = SSL.Connection(dest_context,
                                  dest_sock)

        if hostname:
            ssl_sock.set_tlsext_host_name(hostname)

        ssl_sock.set_connect_state()

        try:
            ssl_sock.do_handshake()

            if self.config["insecure"] == "no":
                verify_hostname(ssl_sock, unicode(hostname))

        # TODO: SSL.Error may have other error types.
        except SSL.Error as e:
            logger.warning(
                "{0}: certificate verification failed.".format(hostname))
            logger.debug(e)
            ssl_sock.close()
            raise

        except VerificationError as e:
            logger.warning(
                "{0}: certificate hostname not matched.".format(hostname))
            logger.debug(e)
            ssl_sock.close()
            raise

        alpn_info = ssl_sock.get_alpn_proto_negotiated() or b"http/1.1"

        logger.debug("{0}:{1} -> Choose {2} as application protocol".format(
            self.context.host, self.context.port, alpn_info))

        self._alpn_future.set_result((ssl_sock,
                                      hostname,
                                      alpn_info))
        return alpn_info

    def src_alpn_callback(self, src_ssl_conn, src_alpn):
        support_alpn = [
            protocol
            for protocol in src_alpn
            if protocol in self.SUPPORT_PROTOCOLS
        ]

        hostname = src_ssl_conn.get_servername()
        alpn_info = self.connect_dest(support_alpn, hostname)

        # NOTE: If the sni hostname is not the same as self.context.host,
        # we use sni hostname instead. Since it's more reliable.
        if hostname and hostname != self.context.host:
            cert, priv_key = self.cert_store.get_cert_and_pkey(hostname)
            ssl_ctx = tls.create_src_sslcontext(
                cert, priv_key)
            src_ssl_conn.set_context(ssl_ctx)

        return bytes(alpn_info)

    def src_info_callback(self, conn, level, ret_code):
        if not level & SSL.SSL_CB_HANDSHAKE_DONE:
            return

        if conn.get_alpn_proto_negotiated() or ret_code != 1:
            return

        logger.debug("handshake withouth alpn, using http/1.1")
        self.connect_dest(["http/1.1"], conn.get_servername())

    @gen.coroutine
    def process_and_return_context(self):
        cert, priv_key = self.cert_store.get_cert_and_pkey(self.context.host)
        src_ssl_ctx = tls.create_src_sslcontext(
            cert, priv_key, alpn_callback=self.src_alpn_callback,
            info_callback=self.src_info_callback)

        try:
            src_stream = yield self.context.src_stream.start_tls(
                server_side=True, ssl_options=src_ssl_ctx)
        except (SSL.Error, VerificationError, StreamClosedError):
            raise SrcStreamClosedError("Certificate Verification Failed")

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
