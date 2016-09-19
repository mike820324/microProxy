import mock
import socket
import unittest

from OpenSSL import SSL
from service_identity import VerificationError
from tornado.locks import Event
from tornado.netutil import add_accept_handler
from tornado.testing import AsyncTestCase, gen_test, bind_unused_port

from microproxy.cert import CertStore
from microproxy.tornado_ext.iostream import MicroProxyIOStream, MicroProxySSLIOStream
from microproxy.protocol.tls import (
    ClientConnection, ServerConnection, create_dest_sslcontext,
    create_src_sslcontext)
from microproxy.utils import HAS_ALPN


class TestServerConnection(AsyncTestCase):
    def setUp(self):
        super(TestServerConnection, self).setUp()
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

        self.cert_store = CertStore(dict(certfile="microproxy/test/test.crt",
                                    keyfile="microproxy/test/test.key"))

    @gen_test
    @unittest.skipIf(not HAS_ALPN, "only support for env with alpn")
    def test_start_tls_with_alpn(self):
        self.on_alpn_records = None

        def on_alpn(conn, alpns):
            self.on_alpn_records = (conn, alpns)

        client_stream_future = self.client_stream.start_tls(
            server_side=False, ssl_options=create_dest_sslcontext(
                insecure=True, trusted_ca_certs="", alpn=["http/1.1"]))

        conn = ServerConnection(self.server_stream)
        server_stream_future = conn.start_tls(
            *self.cert_store.get_cert_and_pkey("127.0.0.1"),
            on_alpn=on_alpn, alpn_resolver=lambda: "http/1.1")

        self.client_stream = yield client_stream_future
        self.assertIsNotNone(self.client_stream)
        self.assertIsInstance(self.client_stream, MicroProxySSLIOStream)
        self.assertFalse(self.client_stream.closed())
        self.assertEqual(
            self.client_stream.fileno().get_alpn_proto_negotiated(),
            b"http/1.1")

        self.server_stream = yield server_stream_future
        self.assertIsNotNone(self.server_stream)
        self.assertIsInstance(self.server_stream, MicroProxySSLIOStream)
        self.assertFalse(self.server_stream.closed())

        # Test on communication between server and client
        yield self.client_stream.write(b"hello")
        data = yield self.server_stream.read_bytes(5)
        self.assertEqual(data, b"hello")

        self.assertIsNotNone(self.on_alpn_records)
        self.assertEqual(self.on_alpn_records[1], ["http/1.1"])

    @gen_test
    @unittest.skipIf(not HAS_ALPN, "only support for env with alpn")
    def test_start_tls_with_alpn_failed(self):
        self.on_alpn_records = None

        def on_alpn(conn, alpns):
            self.on_alpn_records = (conn, alpns)

        client_stream_future = self.client_stream.start_tls(
            server_side=False, ssl_options=create_dest_sslcontext(
                insecure=True, trusted_ca_certs="", alpn=["http/1.1"]))

        conn = ServerConnection(self.server_stream)
        server_stream_future = conn.start_tls(
            *self.cert_store.get_cert_and_pkey("127.0.0.1"),
            on_alpn=on_alpn, alpn_resolver=mock.Mock(side_effect=SSL.Error))

        self.client_stream = yield client_stream_future
        self.assertIsNotNone(self.client_stream)
        self.assertIsInstance(self.client_stream, MicroProxySSLIOStream)
        self.assertFalse(self.client_stream.closed())
        self.assertEqual(
            self.client_stream.fileno().get_alpn_proto_negotiated(),
            b"http/1.1")

        self.server_stream = yield server_stream_future
        self.assertIsNotNone(self.server_stream)
        self.assertIsInstance(self.server_stream, MicroProxySSLIOStream)
        self.assertFalse(self.server_stream.closed())

        self.assertIsNotNone(self.on_alpn_records)
        self.assertEqual(self.on_alpn_records[1], ["http/1.1"])

    @gen_test
    def test_start_tls_without_alpn(self):
        client_stream_future = self.client_stream.start_tls(
            server_side=False, ssl_options=create_dest_sslcontext(
                insecure=True, trusted_ca_certs=""))

        conn = ServerConnection(self.server_stream)
        server_stream_future = conn.start_tls(
            *self.cert_store.get_cert_and_pkey("127.0.0.1"))

        self.client_stream = yield client_stream_future
        self.assertIsNotNone(self.client_stream)
        self.assertIsInstance(self.client_stream, MicroProxySSLIOStream)
        self.assertFalse(self.client_stream.closed())

        self.server_stream = yield server_stream_future
        self.assertIsNotNone(self.server_stream)
        self.assertIsInstance(self.server_stream, MicroProxySSLIOStream)
        self.assertFalse(self.server_stream.closed())

        # Test on communication between server and client
        yield self.client_stream.write(b"hello")
        data = yield self.server_stream.read_bytes(5)
        self.assertEqual(data, b"hello")

    def tearDown(self):
        if self.client_stream and not self.client_stream.closed():
            self.client_stream.close()
        if self.server_stream and not self.server_stream.closed():
            self.server_stream.close()


class TestClientConnection(AsyncTestCase):
    def setUp(self):
        super(TestClientConnection, self).setUp()
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

        self.cert_store = CertStore(dict(certfile="microproxy/test/test.crt",
                                    keyfile="microproxy/test/test.key"))

    if HAS_ALPN:
        @gen_test
        def test_start_tls_with_alpn(self):
            self.record_alpns = None

            def alpn_callback(conn, alpns):
                self.record_alpns = alpns
                return alpns[0]

            server_stream_future = self.server_stream.start_tls(
                server_side=True, ssl_options=create_src_sslcontext(
                    *self.cert_store.get_cert_and_pkey("127.0.0.1"),
                    alpn_callback=alpn_callback))

            conn = ClientConnection(self.client_stream)
            client_stream_future = conn.start_tls(
                insecure=True, trusted_ca_certs="", alpns=[b"http/1.1", b"h2"])

            self.client_stream = yield client_stream_future
            self.assertIsNotNone(self.client_stream)
            self.assertIsInstance(self.client_stream, MicroProxySSLIOStream)
            self.assertFalse(self.client_stream.closed())
            self.assertEqual(
                self.client_stream.fileno().get_alpn_proto_negotiated(),
                b"http/1.1")

            self.server_stream = yield server_stream_future
            self.assertIsNotNone(self.server_stream)
            self.assertIsInstance(self.server_stream, MicroProxySSLIOStream)
            self.assertFalse(self.server_stream.closed())

            # Test on communication between server and client
            yield self.client_stream.write(b"hello")
            data = yield self.server_stream.read_bytes(5)
            self.assertEqual(data, b"hello")

            self.assertEqual(self.record_alpns, [b"http/1.1", b"h2"])

    @gen_test
    def test_start_tls_without_alpn(self):
        server_stream_future = self.server_stream.start_tls(
            server_side=True, ssl_options=create_src_sslcontext(
                *self.cert_store.get_cert_and_pkey("127.0.0.1")))

        conn = ClientConnection(self.client_stream)
        client_stream_future = conn.start_tls(
            insecure=True, trusted_ca_certs="")

        self.client_stream = yield client_stream_future
        self.assertIsNotNone(self.client_stream)
        self.assertIsInstance(self.client_stream, MicroProxySSLIOStream)
        self.assertFalse(self.client_stream.closed())

        self.server_stream = yield server_stream_future
        self.assertIsNotNone(self.server_stream)
        self.assertIsInstance(self.server_stream, MicroProxySSLIOStream)
        self.assertFalse(self.server_stream.closed())

        # Test on communication between server and client
        yield self.client_stream.write(b"hello")
        data = yield self.server_stream.read_bytes(5)
        self.assertEqual(data, b"hello")

    @gen_test
    def test_start_tls_with_truct_cert(self):
        server_stream_future = self.server_stream.start_tls(
            server_side=True, ssl_options=create_src_sslcontext(
                *self.cert_store.get_cert_and_pkey("127.0.0.1")))

        conn = ClientConnection(self.client_stream)
        client_stream_future = conn.start_tls(
            insecure=False, trusted_ca_certs="microproxy/test/test.crt")

        self.client_stream = yield client_stream_future
        self.assertIsNotNone(self.client_stream)
        self.assertIsInstance(self.client_stream, MicroProxySSLIOStream)
        self.assertFalse(self.client_stream.closed())

        self.server_stream = yield server_stream_future
        self.assertIsNotNone(self.server_stream)
        self.assertIsInstance(self.server_stream, MicroProxySSLIOStream)
        self.assertFalse(self.server_stream.closed())

        # Test on communication between server and client
        yield self.client_stream.write(b"hello")
        data = yield self.server_stream.read_bytes(5)
        self.assertEqual(data, b"hello")

    @gen_test
    def test_start_tls_with_not_truct_cert(self):
        server_stream_future = self.server_stream.start_tls(
            server_side=True, ssl_options=create_src_sslcontext(
                *self.cert_store.get_cert_and_pkey("127.0.0.1")))
        self.server_stream = None

        conn = ClientConnection(self.client_stream)
        client_stream_future = conn.start_tls(
            insecure=False, trusted_ca_certs="")
        self.client_stream = None

        with self.assertRaises(SSL.Error):
            yield client_stream_future
        with self.assertRaises((SSL.Error, socket.error)):
            yield server_stream_future

    @gen_test
    def test_start_tls_with_wrong_hostname(self):
        server_stream_future = self.server_stream.start_tls(
            server_side=True, ssl_options=create_src_sslcontext(
                *self.cert_store.get_cert_and_pkey(u"localhost")))

        conn = ClientConnection(self.client_stream)
        client_stream_future = conn.start_tls(
            insecure=False, trusted_ca_certs="microproxy/test/test.crt",
            hostname=u"hello")
        self.client_stream = None

        with self.assertRaises(VerificationError):
            yield client_stream_future

        self.server_stream = yield server_stream_future
        self.assertTrue(self.server_stream.closed())

    def tearDown(self):
        if self.client_stream and not self.client_stream.closed():
            self.client_stream.close()
        if self.server_stream and not self.server_stream.closed():
            self.server_stream.close()
