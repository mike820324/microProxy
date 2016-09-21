import mock
import socket
import unittest

from OpenSSL import SSL
from service_identity import VerificationError
from tornado.iostream import StreamClosedError
from tornado.locks import Event
from tornado.netutil import add_accept_handler
from tornado.testing import AsyncTestCase, gen_test, bind_unused_port

from microproxy.cert import CertStore
from microproxy.context import LayerContext, ServerContext
from microproxy.exception import DestStreamClosedError, ProtocolError, TlsError
from microproxy.tornado_ext.iostream import MicroProxyIOStream, MicroProxySSLIOStream
from microproxy.layer.application.tls import TlsLayer
from microproxy.protocol.tls import create_dest_sslcontext
from microproxy.utils import HAS_ALPN


class TestTlsLayer(AsyncTestCase):
    def setUp(self):
        super(TestTlsLayer, self).setUp()
        self.asyncSetUp()

    @gen_test
    def asyncSetUp(self):
        listener, port = bind_unused_port()
        event = Event()

        def accept_callback(conn, addr):
            self.server_stream = MicroProxyIOStream(conn)
            event.set()

        add_accept_handler(listener, accept_callback)
        self.client_stream = MicroProxyIOStream(socket.socket())
        yield [self.client_stream.connect(('127.0.0.1', port)),
               event.wait()]
        self.io_loop.remove_handler(listener)
        listener.close()

        self.config = dict(
            client_certs="microproxy/test/test.crt", insecure="yes")

        context = LayerContext(mode="socks",
                               src_stream=self.server_stream,
                               dest_stream=mock.Mock(),
                               host="127.0.0.1", port=port)
        self.server_stream = None

        cert_store = CertStore(dict(certfile="microproxy/test/test.crt",
                                    keyfile="microproxy/test/test.key"))
        server_state = ServerContext(cert_store=cert_store, config=self.config)
        self.tls_layer = TlsLayer(server_state, context)

        # NOTE: mock dest conn
        self.tls_dest_stream = mock.Mock()
        self.tls_dest_stream.fileno = mock.Mock(
            return_value=self.tls_dest_stream.socket)
        self.tls_dest_stream.socket.get_alpn_proto_negotiated = mock.Mock(
            return_value=b"http/1.1")
        self.dest_conn = mock.Mock()
        self.dest_conn.start_tls_blocking = mock.Mock(
            return_value=self.tls_dest_stream)
        self.tls_layer.dest_conn = self.dest_conn

    @gen_test
    @unittest.skipIf(not HAS_ALPN, "only support for env with alpn")
    def test_success_on_http1(self):
        client_stream_future = self.client_stream.start_tls(
            server_side=False,
            ssl_options=create_dest_sslcontext(
                insecure=True, alpn=["http/1.1", "h2"]))
        self.client_stream = None

        ctx_future = self.tls_layer.process_and_return_context()

        ctx = yield ctx_future
        self.assertIsNotNone(ctx)

        self.server_stream = ctx.src_stream
        self.assertIsInstance(self.server_stream, MicroProxySSLIOStream)
        self.assertFalse(self.server_stream.closed())
        self.assertIs(ctx.dest_stream, self.tls_dest_stream)
        self.assertEqual(ctx.scheme, "https")

        # Test on client that handshaking is completed
        self.client_stream = yield client_stream_future
        self.assertIsInstance(self.client_stream, MicroProxySSLIOStream)
        self.assertFalse(self.client_stream.closed())

        # Test on that the connection between client and proxy is worked
        self.client_stream.write(b"hello")
        data = yield self.server_stream.read_bytes(5)
        self.assertEqual(data, b"hello")

        self.tls_dest_stream.socket.get_alpn_proto_negotiated.assert_called_with()
        self.dest_conn.start_tls_blocking.assert_called_with(
            insecure=True, trusted_ca_certs="microproxy/test/test.crt",
            hostname="127.0.0.1", alpns=["http/1.1", "h2"])

    @gen_test
    @unittest.skipIf(not HAS_ALPN, "only support for env with alpn")
    def test_success_on_h2(self):
        self.tls_dest_stream.socket.get_alpn_proto_negotiated = mock.Mock(
            return_value=b"h2")

        client_stream_future = self.client_stream.start_tls(
            server_side=False,
            ssl_options=create_dest_sslcontext(
                insecure=True, alpn=["http/1.1", "h2"]))
        self.client_stream = None

        ctx_future = self.tls_layer.process_and_return_context()

        ctx = yield ctx_future
        self.assertIsNotNone(ctx)

        self.server_stream = ctx.src_stream
        self.assertIsInstance(self.server_stream, MicroProxySSLIOStream)
        self.assertFalse(self.server_stream.closed())
        self.assertIs(ctx.dest_stream, self.tls_dest_stream)
        self.assertEqual(ctx.scheme, "h2")

        # Test on client that handshaking is completed
        self.client_stream = yield client_stream_future
        self.assertIsInstance(self.client_stream, MicroProxySSLIOStream)
        self.assertFalse(self.client_stream.closed())

        # Test on that the connection between client and proxy is worked
        self.client_stream.write(b"hello")
        data = yield self.server_stream.read_bytes(5)
        self.assertEqual(data, b"hello")

        self.tls_dest_stream.socket.get_alpn_proto_negotiated.assert_called_with()
        self.dest_conn.start_tls_blocking.assert_called_with(
            insecure=True, trusted_ca_certs="microproxy/test/test.crt",
            hostname="127.0.0.1", alpns=["http/1.1", "h2"])

    @gen_test
    @unittest.skipIf(not HAS_ALPN, "only support for env with alpn")
    def test_success_on_spdy(self):
        self.tls_dest_stream.socket.get_alpn_proto_negotiated = mock.Mock(
            return_value=b"spdy/2")

        client_stream_future = self.client_stream.start_tls(
            server_side=False,
            ssl_options=create_dest_sslcontext(
                insecure=True, alpn=["http/1.1", "spdy/2", "h2"]))
        self.client_stream = None

        ctx_future = self.tls_layer.process_and_return_context()

        with self.assertRaises(ProtocolError):
            yield ctx_future

        self.client_stream = yield client_stream_future
        self.assertTrue(self.client_stream.closed())

    @gen_test
    def test_success_without_alpn(self):
        client_stream_future = self.client_stream.start_tls(
            server_side=False,
            ssl_options=create_dest_sslcontext(insecure=True))
        self.client_stream = None

        ctx_future = self.tls_layer.process_and_return_context()

        ctx = yield ctx_future
        self.assertIsNotNone(ctx)

        self.server_stream = ctx.src_stream
        self.assertIsInstance(self.server_stream, MicroProxySSLIOStream)
        self.assertFalse(self.server_stream.closed())
        self.assertIs(ctx.dest_stream, self.tls_dest_stream)
        self.assertEqual(ctx.scheme, "https")

        # Test on client that handshaking is completed
        self.client_stream = yield client_stream_future
        self.assertIsInstance(self.client_stream, MicroProxySSLIOStream)
        self.assertFalse(self.client_stream.closed())

        # Test on that the connection between client and proxy is worked
        self.client_stream.write(b"hello")
        data = yield self.server_stream.read_bytes(5)
        self.assertEqual(data, b"hello")

        self.tls_dest_stream.socket.get_alpn_proto_negotiated.assert_called_with()
        self.dest_conn.start_tls_blocking.assert_called_with(
            insecure=True, trusted_ca_certs="microproxy/test/test.crt",
            hostname="127.0.0.1", alpns=["http/1.1"])

    @gen_test
    def test_dest_handshaking_failed_with_verifycation_error(self):
        self.dest_conn.start_tls_blocking = mock.Mock(
            side_effect=VerificationError("error"))
        self.config.update(dict(insecure="no"))

        client_stream_future = self.client_stream.start_tls(
            server_side=False,
            ssl_options=create_dest_sslcontext(insecure=True))
        self.client_stream = None

        ctx_future = self.tls_layer.process_and_return_context()

        with self.assertRaises(TlsError):
            yield ctx_future

        self.client_stream = yield client_stream_future
        self.assertIsNotNone(self.client_stream)
        self.assertTrue(self.client_stream.closed())

        self.dest_conn.start_tls_blocking.assert_called_with(
            insecure=False, trusted_ca_certs="microproxy/test/test.crt",
            hostname="127.0.0.1", alpns=["http/1.1"])

    @gen_test
    def test_dest_handshaking_failed_with_ssl_error(self):
        self.dest_conn.start_tls_blocking = mock.Mock(
            side_effect=SSL.Error)

        client_stream_future = self.client_stream.start_tls(
            server_side=False,
            ssl_options=create_dest_sslcontext(insecure=True))
        self.client_stream = None

        ctx_future = self.tls_layer.process_and_return_context()

        with self.assertRaises(TlsError):
            yield ctx_future

        self.client_stream = yield client_stream_future
        self.assertIsNotNone(self.client_stream)
        self.assertTrue(self.client_stream.closed())

        self.dest_conn.start_tls_blocking.assert_called_with(
            insecure=True, trusted_ca_certs="microproxy/test/test.crt",
            hostname="127.0.0.1", alpns=["http/1.1"])

    @gen_test
    def test_dest_handshaking_failed_with_stream_closed(self):
        self.dest_conn.start_tls_blocking = mock.Mock(
            side_effect=StreamClosedError)

        client_stream_future = self.client_stream.start_tls(
            server_side=False,
            ssl_options=create_dest_sslcontext(insecure=True))
        self.client_stream = None

        ctx_future = self.tls_layer.process_and_return_context()

        with self.assertRaises(DestStreamClosedError):
            yield ctx_future

        self.client_stream = yield client_stream_future
        self.assertIsNotNone(self.client_stream)
        self.assertTrue(self.client_stream.closed())

        self.dest_conn.start_tls_blocking.assert_called_with(
            insecure=True, trusted_ca_certs="microproxy/test/test.crt",
            hostname="127.0.0.1", alpns=["http/1.1"])

    @gen_test
    def test_failed_with_client_closed(self):
        ctx_future = self.tls_layer.process_and_return_context()
        self.client_stream.close()

        with self.assertRaises(TlsError):
            yield ctx_future

    def tearDown(self):
        if self.client_stream and not self.client_stream.closed():
            self.client_stream.close()
        if self.server_stream and not self.server_stream.closed():
            self.server_stream.close()
