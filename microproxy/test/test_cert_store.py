import unittest

from microproxy.cert import CertStore
from OpenSSL import crypto


class CertStoreTest(unittest.TestCase):
    def setUp(self):
        config = {
            "certfile": "microproxy/test/test.crt",
            "keyfile": "microproxy/test/test.key"
        }

        self.cert_store = CertStore(config)

    def test_create_cert(self):
        cn = "www.test.com"
        cert = self.cert_store.create_cert(cn)

        ca_root = self.cert_store.ca_root
        # pkey = self.cert_store.private_key

        self.assertIsInstance(cert, crypto.X509)
        self.assertEqual(2, cert.get_version())
        self.assertEqual(ca_root.get_subject(), cert.get_issuer())
        # TODO: Need to find a way to test whether the pkey content is equal.
        # self.assertEqual(pkey._pkey, cert.get_pubkey()._pkey)
        self.assertEquals(unicode(cn), cert.get_subject().CN)

    def test_get_cert_from_cache_nonexist(self):
        cert = self.cert_store.get_cert_from_cache("www.abc.com")
        self.assertIsNone(cert)

    def test_get_cert_from_cache_exist(self):
        orig_cert = self.cert_store.create_cert("www.abc.com")
        new_cert = self.cert_store.get_cert_from_cache("www.abc.com")

        self.assertIsInstance(new_cert, crypto.X509)
        self.assertEqual(orig_cert, new_cert)

    def test_get_cert_and_pkey(self):
        old_ca, old_pkey = self.cert_store.get_cert_and_pkey("www.abc.com")

        self.assertIsInstance(old_ca, crypto.X509)
        self.assertIsInstance(old_pkey, crypto.PKey)

        new_ca, new_pkey = self.cert_store.get_cert_and_pkey("www.abc.com")

        self.assertIsInstance(new_ca, crypto.X509)
        self.assertIsInstance(new_pkey, crypto.PKey)
        self.assertEqual(old_ca, new_ca)
        self.assertEqual(old_pkey, new_pkey)
