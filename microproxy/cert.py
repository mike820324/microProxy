from OpenSSL import crypto
import time

from microproxy.utils import get_logger
logger = get_logger(__name__)


class CertStore(object):
    def __init__(self, config):
        self.config = config
        self.ca_root, self.private_key = self._get_root()
        self.certs_cache = dict()

    def _get_root(self):
        root_ca_file = self.config["certfile"]
        with open(root_ca_file, "rb") as fp:
            _buffer = fp.read()
        ca_root = crypto.load_certificate(crypto.FILETYPE_PEM, _buffer)

        private_key_file = self.config["keyfile"]
        with open(private_key_file, "rb") as fp:
            _buffer = fp.read()
        private_key = crypto.load_privatekey(crypto.FILETYPE_PEM, _buffer)

        return (ca_root, private_key)

    def get_cert(self, common_name):
        cert = self.get_cert_from_cache(common_name)
        if cert:
            return cert

        if common_name.startswith(b"www"):
            wildcard_common_name = b"*" + common_name[3:]
            cert = self.create_cert(wildcard_common_name)
            self.certs_cache[wildcard_common_name] = cert
        else:
            cert = self.create_cert(common_name)
            self.certs_cache[common_name] = cert
        return cert

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

        logger.debug("create cert with commonname: {0}".format(common_name))
        return (cert, self.private_key)

    def get_potention_common_names(self, common_name):
        if "." not in common_name:
            return [common_name]
        wildcard_common_name = b"*" + common_name[
            common_name.index("."):]
        return [wildcard_common_name, common_name]

    def get_cert_from_cache(self, common_name):
        potential_common_names = self.get_potention_common_names(common_name)
        match_names = filter(
            lambda key: key in self.certs_cache,
            potential_common_names)
        match_name = match_names[0] if match_names else None
        if match_name:
            logger.debug("get cert commonname:{0} from cache with {1}".format(
                match_name, common_name))
            return self.certs_cache[match_name]
        return None
