from copy import copy
from OpenSSL import SSL
import certifi
from service_identity import VerificationError
from tornado import gen, concurrent
from tornado.iostream import StreamClosedError

from microproxy.utils import HAS_ALPN, get_logger
from microproxy.protocol import tls
from microproxy.cert import get_cert_store
from microproxy.exception import (
    DestStreamClosedError, TlsError, ProtocolError)

logger = get_logger(__name__)


class TlsLayer(object):
    SUPPORT_PROTOCOLS = ["http/1.1", "h2"]

    def __init__(self, context, cert_store=None):
        super(TlsLayer, self).__init__()
        self.context = copy(context)
        self.config = self.context.config
        self.cert_store = cert_store or get_cert_store()
        # NOTE: tuple contains (dest_ssl_conn, hostname, alpn_info)
        # Throws exception if failed
        self._dest_stream_future = concurrent.Future()
        self._server_hostname = None

        self.src_conn = tls.ServerConnection(self.context.src_stream)
        self.dest_conn = tls.ClientConnection(self.context.dest_stream)

    def start_dest_tls(self, support_alpns, hostname):
        logger.debug("start dest tls handshaking: {0}".format(hostname))
        trusted_ca_certs = self.config["client_certs"] or certifi.where()
        try:
            logger.debug("running dest conn tls handshaking")
            dest_stream = self.dest_conn.start_tls_blocking(
                insecure=(self.config["insecure"] == "yes"),
                trusted_ca_certs=trusted_ca_certs, hostname=hostname,
                alpns=support_alpns)
            logger.debug("finish dest conn tls handshake")
        except Exception as e:
            logger.debug("dest tls handshaking failed with {0}".format(str(e)))
            self._dest_stream_future.set_exception(e)
        else:
            select_alpn = (dest_stream.fileno().get_alpn_proto_negotiated() or
                           b"http/1.1")
            logger.debug("{0}:{1} -> Choose {2} as application protocol".format(
                self.context.host, self.context.port, select_alpn))
            self._dest_stream_future.set_result(
                (dest_stream, hostname, select_alpn))

    def start_dest_tls_with_alpns(self, src_ssl_conn, src_alpns):
        """Alpn select callback on source socket
        that wil also do server side tls handshaking and alpn/sni check
        """
        logger.debug("source alpn start: {0}".format(src_alpns))
        support_alpns = [
            protocol
            for protocol in src_alpns
            if protocol in self.SUPPORT_PROTOCOLS
        ]
        hostname = src_ssl_conn.get_servername() or self.context.host
        self.start_dest_tls(support_alpns, hostname)

    def src_info_callback(self, conn, level, ret_code):
        if not level & SSL.SSL_CB_HANDSHAKE_DONE:
            return
        if (HAS_ALPN and conn.get_alpn_proto_negotiated()) or ret_code != 1:
            return
        logger.debug("handshake withouth alpn, using http/1.1")
        self.start_dest_tls(["http/1.1"], conn.get_servername() or self.context.host)

    def resolve_select_alpn(self):
        _, _, select_alpn = self._dest_stream_future.result()
        return select_alpn

    @gen.coroutine
    def process_and_return_context(self):
        try:
            src_stream = yield self.src_conn.start_tls(
                *self.cert_store.get_cert_and_pkey(self.context.host),
                info_callback=self.src_info_callback,
                on_alpn=self.start_dest_tls_with_alpns,
                alpn_resolver=self.resolve_select_alpn)
        # TODO: SSL.Error may have other error types.
        except SSL.Error as e:
            raise TlsError("Tls Handshaking Failed on source with: ({0}) {1}".format(
                type(e).__name__, str(e)))

        try:
            dest_stream, hostname, alpn_info = yield self._dest_stream_future
        # TODO: SSL.Error may have other error types.
        except (SSL.Error, VerificationError) as e:
            src_stream.close()
            raise TlsError("Tls Handshaking Failed on destination with: ({0}) {1}".format(
                type(e).__name__, str(e)))
        except StreamClosedError as e:
            src_stream.close()
            raise DestStreamClosedError(self, detail="Stream closed when tls Handshaking failed")

        self.context.src_stream = src_stream
        self.context.dest_stream = dest_stream
        if hostname:
            self.context.host = hostname
        if alpn_info == "http/1.1":
            self.context.scheme = "https"
        elif alpn_info == "h2":
            self.context.scheme = "h2"
        else:
            self.context.src_stream.close()
            self.context.dest_stream.close()
            raise ProtocolError("Not supported protocol from alpn: {0}".format(alpn_info))

        raise gen.Return(self.context)
