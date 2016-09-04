from OpenSSL import SSL, crypto
from service_identity import VerificationError
from service_identity.pyopenssl import verify_hostname

from microproxy.utils import get_logger
logger = get_logger(__name__)

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

    if not insecure and trusted_ca_certs:
        verify_mode = SSL.VERIFY_PEER | SSL.VERIFY_FAIL_IF_NO_PEER_CERT
        ssl_ctx.load_verify_locations(trusted_ca_certs)
    else:
        verify_mode = SSL.VERIFY_NONE

    ssl_ctx.set_verify(verify_mode, certificate_verify_cb)
    try:
        ssl_ctx.set_alpn_protos(alpn or [])
    except NotImplementedError:
        pass

    return ssl_ctx


def create_src_sslcontext(cert, priv_key, alpn_callback=None,
                          info_callback=None):
    ssl_ctx = create_basic_sslcontext()
    ssl_ctx.use_certificate(cert)
    ssl_ctx.use_privatekey(priv_key)

    if alpn_callback:
        ssl_ctx.set_alpn_select_callback(alpn_callback)
    if info_callback:
        ssl_ctx.set_info_callback(info_callback)

    return ssl_ctx
