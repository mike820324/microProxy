from __future__ import absolute_import

from OpenSSL import SSL, crypto
import certifi
import construct

from tornado import gen
from microproxy.pyca_tls import _constructs
from microproxy.utils import HAS_ALPN
from microproxy.exception import ProtocolError

from microproxy.log import ProxyLogger
logger = ProxyLogger.get_logger(__name__)

_SUPPROT_CIPHERS_SUITES = (
    "ECDHE-RSA-AES128-GCM-SHA256",
    "ECDHE-ECDSA-AES128-GCM-SHA256",
    "ECDHE-RSA-AES256-GCM-SHA384",
    "ECDHE-ECDSA-AES256-GCM-SHA384",
    "DHE-RSA-AES128-GCM-SHA256",
    "DHE-DSS-AES128-GCM-SHA256",
    "kEDH+AESGCM",
    "ECDHE-RSA-AES128-SHA256",
    "ECDHE-ECDSA-AES128-SHA256",
    "ECDHE-RSA-AES128-SHA",
    "ECDHE-ECDSA-AES128-SHA",
    "ECDHE-RSA-AES256-SHA384",
    "ECDHE-ECDSA-AES256-SHA384",
    "ECDHE-RSA-AES256-SHA",
    "ECDHE-ECDSA-AES256-SHA",
    "DHE-RSA-AES128-SHA256",
    "DHE-RSA-AES128-SHA",
    "DHE-DSS-AES128-SHA256",
    "DHE-RSA-AES256-SHA256",
    "DHE-DSS-AES256-SHA",
    "DHE-RSA-AES256-SHA",
    "ECDHE-RSA-DES-CBC3-SHA",
    "ECDHE-ECDSA-DES-CBC3-SHA",
    "AES128-GCM-SHA256",
    "AES256-GCM-SHA384",
    "AES128-SHA256",
    "AES256-SHA256",
    "AES128-SHA",
    "AES256-SHA",
    "AES",
    "DES-CBC3-SHA",
    "HIGH",
    "!aNULL",
    "!eNULL",
    "!EXPORT",
    "!DES",
    "!RC4",
    "!MD5",
    "!PSK",
    "!aECDH",
    "!EDH-DSS-DES-CBC3-SHA",
    "!EDH-RSA-DES-CBC3-SHA",
    "!KRB5-DES-CBC3-SHA"
)


def create_basic_sslcontext():
    ssl_ctx = SSL.Context(SSL.SSLv23_METHOD)
    ssl_ctx.set_options(SSL.OP_NO_SSLv2 | SSL.OP_NO_SSLv3 | SSL.OP_CIPHER_SERVER_PREFERENCE)

    ssl_ctx.set_cipher_list(":".join(_SUPPROT_CIPHERS_SUITES))

    # NOTE: cipher suite related to ECDHE will need this
    ssl_ctx.set_tmp_ecdh(crypto.get_elliptic_curve('prime256v1'))
    return ssl_ctx


def certificate_verify_cb(conn, x509, err_num, err_depth, verify_status):
    return verify_status


def create_dest_sslcontext(insecure=False, trusted_ca_certs="", alpn=None):
    ssl_ctx = create_basic_sslcontext()

    if not insecure:
        trusted_ca_certs = trusted_ca_certs or certifi.where()
        ssl_ctx.load_verify_locations(trusted_ca_certs)
        ssl_ctx.set_verify(
            SSL.VERIFY_PEER | SSL.VERIFY_FAIL_IF_NO_PEER_CERT,
            certificate_verify_cb)
    else:
        ssl_ctx.set_verify(SSL.VERIFY_NONE, certificate_verify_cb)

    if alpn and HAS_ALPN:
        ssl_ctx.set_alpn_protos(alpn)

    return ssl_ctx


def create_src_sslcontext(cert, priv_key, alpn_callback=None,
                          info_callback=None):
    ssl_ctx = create_basic_sslcontext()
    ssl_ctx.use_certificate(cert)
    ssl_ctx.use_privatekey(priv_key)

    if alpn_callback and HAS_ALPN:
        ssl_ctx.set_alpn_select_callback(alpn_callback)
    if info_callback:
        ssl_ctx.set_info_callback(info_callback)

    return ssl_ctx


class TlsClientHello(object):
    SUPPORT_PROTOCOLS = ["http/1.1", "h2"]

    def __init__(self, raw_client_hello):
        try:
            self._client_hello = _constructs.ClientHello.parse(raw_client_hello)
        except construct.ConstructError as e:
            raise ProtocolError(
                'Cannot parse Client Hello: {0}, Raw Client Hello: {1}'.format(
                    repr(e), raw_client_hello.encode("hex"))
            )

    def raw(self):
        return self._client_hello

    @property
    def cipher_suites(self):
        return self._client_hello.cipher_suites.cipher_suites

    @property
    def sni(self):
        # TODO: hostname validation is required.
        for extension in self._client_hello.extensions:
            is_valid_sni_extension = (
                extension.type == 0x00 and
                len(extension.server_names) == 1 and
                extension.server_names[0].type == 0)

            if is_valid_sni_extension:
                return extension.server_names[0].name.decode("idna")

    @property
    def alpn_protocols(self):
        for extension in self._client_hello.extensions:
            if extension.type == 0x10:
                return [
                    bytes(protocol)
                    for protocol in list(extension.alpn_protocols)
                    if protocol in self.SUPPORT_PROTOCOLS
                ]

    def __repr__(self):
        return "TlsClientHello( sni: %s alpn_protocols: %s,  cipher_suites: %s)" % \
            (self.sni, self.alpn_protocols, self.cipher_suites)


class ServerConnection(object):
    def __init__(self, stream):
        self.stream = stream
        self.alpn_resolver = None
        self.on_alpn = None

    def start_tls(self, cert, priv_key, select_alpn=None):
        self.select_alpn = select_alpn
        ssl_ctx = create_src_sslcontext(
            cert, priv_key, alpn_callback=self.alpn_callback)
        return self.stream.start_tls(server_side=True, ssl_options=ssl_ctx)

    def alpn_callback(self, conn, alpns):
        return self.select_alpn


class ClientConnection(object):
    def __init__(self, stream):
        self.stream = stream

    @gen.coroutine
    def start_tls(self, insecure=False, trusted_ca_certs="",
                  hostname=None, alpns=None):
        ssl_ctx = create_dest_sslcontext(insecure, trusted_ca_certs, alpns)
        stream = yield self.stream.start_tls(
            server_side=False, ssl_options=ssl_ctx, server_hostname=hostname)

        raise gen.Return(stream)
