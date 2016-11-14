from OpenSSL import crypto
import time

from microproxy.log import ProxyLogger
logger = ProxyLogger.get_logger(__name__)


class CertStore(object):
    def __init__(self, config):
        self.ca_root, self.private_key = self._get_root(
            config["certfile"], config["keyfile"])
        self.certs_cache = dict()

    def _get_root(self, certfile, keyfile):
        root_ca_file = certfile
        with open(root_ca_file, "rb") as fp:
            _buffer = fp.read()
        ca_root = crypto.load_certificate(crypto.FILETYPE_PEM, _buffer)

        private_key_file = keyfile
        with open(private_key_file, "rb") as fp:
            _buffer = fp.read()
        private_key = crypto.load_privatekey(crypto.FILETYPE_PEM, _buffer)

        return (ca_root, private_key)

    def get_cert_and_pkey(self, common_name):
        cert = self.get_cert_from_cache(common_name)
        if cert:
            logger.debug("get cert commonname:{0} from cache".format(
                common_name))
            return (cert, self.private_key)
        else:
            logger.debug("create cert commonname:{0} to cache".format(
                common_name))
            cert = self.create_cert(common_name)
            return (cert, self.private_key)

    def create_cert(self, common_name):
        cert = crypto.X509()

        # NOTE: Expire time 3 yr
        cert.set_serial_number(int(time.time() * 10000))
        cert.gmtime_adj_notBefore(-3600 * 48)
        cert.gmtime_adj_notAfter(94608000)
        cert.get_subject().CN = common_name

        cert.set_issuer(self.ca_root.get_subject())
        cert.set_pubkey(self.ca_root.get_pubkey())
        cert.set_version(2)
        cert.sign(self.private_key, "sha256")

        self.certs_cache[common_name] = cert
        return cert

    def get_cert_from_cache(self, common_name):
        try:
            return self.certs_cache[common_name]
        except KeyError:
            return None
