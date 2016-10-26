from __future__ import absolute_import

from copy import copy
import struct
from OpenSSL import SSL
import certifi
from service_identity import VerificationError
from tornado import gen

from microproxy.utils import get_logger
from microproxy.protocol.tls import TlsClientHello, ServerConnection, ClientConnection
from microproxy.exception import (
    DestStreamClosedError, TlsError, ProtocolError)

logger = get_logger(__name__)


class TlsLayer(object):
    def __init__(self, server_state, context):
        super(TlsLayer, self).__init__()
        self.context = copy(context)
        self.config = server_state.config
        self.cert_store = server_state.cert_store

        self.src_conn = ServerConnection(self.context.src_stream)
        self.dest_conn = ClientConnection(self.context.dest_stream)

    def peek_client_hello(self):
        client_hello = b""
        client_hello_size = 1
        offset = 0
        while len(client_hello) < client_hello_size:
            record_header = self.context.src_stream.peek(offset + 5)[offset:]
            if len(record_header) != 5:
                raise ProtocolError(
                    'Expected TLS record, got "{}" instead.'.format(record_header))

            record_size = struct.unpack("!H", record_header[3:])[0] + 5
            record_body = self.context.src_stream.peek(offset + record_size)[offset + 5:]
            if len(record_body) != record_size - 5:
                raise ProtocolError(
                    "Unexpected EOF in TLS handshake: {}".format(record_body))

            client_hello += record_body
            offset += record_size
            client_hello_size = struct.unpack("!I", b'\x00' + client_hello[1:4])[0] + 4

        return client_hello

    @gen.coroutine
    def start_dest_tls(self, hostname, client_alpns):
        trusted_ca_certs = self.config["client_certs"] or certifi.where()

        try:
            logger.debug("start dest tls handshaking: {0}".format(hostname))
            dest_stream = yield self.dest_conn.start_tls(
                insecure=self.config["insecure"],
                trusted_ca_certs=trusted_ca_certs,
                hostname=hostname, alpns=client_alpns)

        # TODO: tornado_ext.iostream should handle this part.
        except SSL.SysCallError as e:
            raise DestStreamClosedError(self, detail="Stream closed when tls Handshaking failed")

        except (SSL.Error, VerificationError) as e:
            raise TlsError("Tls Handshaking Failed on destination with: ({0}) {1}".format(
                type(e).__name__, str(e)))

        else:
            logger.debug(dest_stream.fileno().get_alpn_proto_negotiated())
            select_alpn = (dest_stream.fileno().get_alpn_proto_negotiated() or
                           b"http/1.1")

            logger.debug("{0}:{1} -> Choose {2} as application protocol".format(
                self.context.host, self.context.port, select_alpn))
            logger.debug("finish dest tls handshake")
            raise gen.Return((dest_stream, select_alpn))

    @gen.coroutine
    def start_src_tls(self, hostname, select_alpn):
        try:
            logger.debug("start src tls handshaking: {0}".format(hostname))
            src_stream = yield self.src_conn.start_tls(
                *self.cert_store.get_cert_and_pkey(hostname),
                select_alpn=select_alpn)

        except SSL.Error as e:
            raise TlsError("Tls Handshaking Failed on source with: ({0}) {1}".format(
                type(e).__name__, str(e)))

        else:
            logger.debug("finish src tls handshake")
            raise gen.Return(src_stream)

    def update_layer_context(self,
                             src_stream,
                             dest_stream,
                             hostname,
                             select_alpn):

        self.context.src_stream = src_stream
        self.context.dest_stream = dest_stream
        if hostname:
            self.context.host = hostname
        if select_alpn == "http/1.1":
            self.context.scheme = "https"
        elif select_alpn == "h2":
            self.context.scheme = "h2"
        else:
            src_stream.close()
            dest_stream.close()
            raise ProtocolError("Unsupported alpn protocol: {0}".format(select_alpn))

    @gen.coroutine
    def process_and_return_context(self):
        # NOTE: peeking src stream client hello.
        raw_client_hello = self.peek_client_hello()
        client_hello = TlsClientHello(raw_client_hello[4:])

        hostname = client_hello.sni or self.context.host
        try:
            dest_stream, select_alpn = yield self.start_dest_tls(
                hostname, client_hello.alpn_protocols)
        except:
            if not self.context.src_stream.closed():
                self.context.src_stream.close()
            raise

        try:
            src_stream = yield self.start_src_tls(
                hostname, select_alpn)

        except:
            if not dest_stream.closed():
                dest_stream.close()
            raise

        self.update_layer_context(
            src_stream, dest_stream, hostname, select_alpn)

        raise gen.Return(self.context)
