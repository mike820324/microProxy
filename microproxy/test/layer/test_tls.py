import mock
import unittest

from OpenSSL import SSL
from service_identity import VerificationError
from tornado.iostream import StreamClosedError
from tornado.testing import gen_test

from microproxy.test.utils import ProxyAsyncTestCase
from microproxy.cert import CertStore
from microproxy.context import LayerContext, ServerContext
from microproxy.exception import DestStreamClosedError, ProtocolError, TlsError
from microproxy.tornado_ext.iostream import MicroProxySSLIOStream
from microproxy.layer.application.tls import TlsLayer
from microproxy.protocol.tls import create_dest_sslcontext, create_basic_sslcontext
from microproxy.utils import HAS_ALPN


def create_src_sslcontext(cert, priv_key, alpn_callback):
    ssl_ctx = create_basic_sslcontext()
    ssl_ctx.use_certificate_file(cert)
    ssl_ctx.use_privatekey_file(priv_key)

    if alpn_callback and HAS_ALPN:
        ssl_ctx.set_alpn_select_callback(alpn_callback)

    return ssl_ctx

class TestTlsLayer(ProxyAsyncTestCase):
    def setUp(self):
        super(TestTlsLayer, self).setUp()
        self.asyncSetUp()

    @gen_test
    def asyncSetUp(self):
        self.client_stream, src_stream = yield self.create_iostream_pair()
        dest_stream, self.server_stream = yield self.create_iostream_pair()

        self.config = dict(
            client_certs="microproxy/test/test.crt", insecure="yes")

        cert_store = CertStore(dict(certfile="microproxy/test/test.crt",
                                    keyfile="microproxy/test/test.key"))
        server_state = ServerContext(cert_store=cert_store, config=self.config)

        # src_stream.pause()
        context = LayerContext(mode="socks",
                               src_stream=src_stream,
                               dest_stream=dest_stream,
                               host="127.0.0.1", port="443")

        self.tls_layer = TlsLayer(server_state, context)

    @gen_test
    @unittest.skipIf(not HAS_ALPN, "only support for env with alpn")
    def test_start_dest_tls_with_alpn_http1(self):
        def alpn_callback(conn, alpns):
            if "http/1.1" not in alpns:
                raise ValueError("incorrect alpns")
            return b"http/1.1"

        server_stream_future = self.server_stream.start_tls(
            server_side=True,
            ssl_options=create_src_sslcontext(
                "microproxy/test/test.crt", "microproxy/test/test.key",
                alpn_callback=alpn_callback))

        ctx_future = self.tls_layer.start_dest_tls("www.google.com", ["http/1.1"])

        dest_stream, alpn = yield ctx_future
        self.assertIsInstance(dest_stream, MicroProxySSLIOStream)
        self.assertFalse(dest_stream.closed())
        self.assertEqual(alpn, "http/1.1")

        self.server_stream = yield server_stream_future

        dest_stream.write(b"hello")
        data = yield self.server_stream.read_bytes(5)
        self.assertEqual(data, b"hello")

    @gen_test
    @unittest.skipIf(not HAS_ALPN, "only support for env with alpn")
    def test_start_dest_tls_with_alpn_h2(self):
        def alpn_callback(conn, alpns):
            if "h2" not in alpns:
                raise ValueError("incorrect alpns")
            return b"h2"

        server_stream_future = self.server_stream.start_tls(
            server_side=True,
            ssl_options=create_src_sslcontext(
                "microproxy/test/test.crt", "microproxy/test/test.key",
                alpn_callback=alpn_callback))

        ctx_future = self.tls_layer.start_dest_tls("www.google.com", ["http/1.1", "h2"])

        dest_stream, alpn = yield ctx_future
        self.assertIsInstance(dest_stream, MicroProxySSLIOStream)
        self.assertFalse(dest_stream.closed())
        self.assertEqual(alpn, "h2")

        self.server_stream = yield server_stream_future

        dest_stream.write(b"hello")
        data = yield self.server_stream.read_bytes(5)
        self.assertEqual(data, b"hello")

    @gen_test
    def test_start_dest_tls_with_verification_error(self):
        self.config.update(dict(insecure="no"))

        def alpn_callback(conn, alpns):
            return b""

        server_stream_future = self.server_stream.start_tls(
            server_side=True,
            ssl_options=create_src_sslcontext(
                "microproxy/test/test.crt", "microproxy/test/test.key",
                alpn_callback=alpn_callback))

        ctx_future = self.tls_layer.start_dest_tls("www.google.com", [])

        with self.assertRaises(TlsError):
            dest_stream, alpn = yield ctx_future

        self.server_stream = yield server_stream_future

    @gen_test
    def test_start_dest_tls_with_ssl_error(self):
        server_stream_future = self.server_stream.start_tls(
            server_side=True,
            ssl_options=create_src_sslcontext(
                "microproxy/test/test.crt", "microproxy/test/test.key",
                alpn_callback=None))

        self.config.update({"insecure": "no"})
        ctx_future = self.tls_layer.start_dest_tls("www.google.com", [])

        with self.assertRaises(TlsError):
            dest_stream, alpn = yield ctx_future

        self.server_stream = yield server_stream_future

    @gen_test
    def test_start_dest_tls_with_dest_stream_closed(self):
        ctx_future = self.tls_layer.start_dest_tls("www.google.com", [])
        self.server_stream.close()

        with self.assertRaises(DestStreamClosedError):
            dest_stream, alpn = yield ctx_future

    def tearDown(self):
        if self.client_stream and not self.client_stream.closed():
            self.client_stream.close()
        if self.server_stream and not self.server_stream.closed():
            self.server_stream.close()
