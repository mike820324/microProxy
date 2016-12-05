import errno
from mock import Mock

from ipaddress import IPv4Address
from tornado.gen import TimeoutError
from tornado.testing import gen_test, bind_unused_port
from tornado.iostream import StreamClosedError
from tornado.netutil import add_accept_handler

from microproxy.test.utils import ProxyAsyncTestCase
from microproxy.context import LayerContext
from microproxy.layer import SocksLayer
from microproxy.exception import ProtocolError, DestNotConnectedError, SrcStreamClosedError
from microproxy.tornado_ext.iostream import MicroProxyIOStream

from socks5 import GreetingRequest, Request
from socks5 import GreetingResponse, Response
from socks5 import RESP_STATUS, AUTH_TYPE, REQ_COMMAND, ADDR_TYPE
from socks5 import Connection


class TestSocksProxyHandler(ProxyAsyncTestCase):
    def setUp(self):
        super(TestSocksProxyHandler, self).setUp()
        self.asyncSetUp()
        self.event = None

    @gen_test
    def asyncSetUp(self):
        self.client_stream, self.src_stream = yield self.create_iostream_pair()

        self.context = LayerContext(
            mode="socks", src_stream=self.src_stream)
        self.layer = SocksLayer(self.context)

        self.listener, self.port = bind_unused_port()

        def dest_accept_callback(conn, addr):
            self.dest_server_stream = MicroProxyIOStream(conn)
            self.addCleanup(self.dest_server_stream.close)

        add_accept_handler(self.listener, dest_accept_callback)
        self.addCleanup(self.listener.close)

    def collect_send_event(self, event):
        self.event = event
        return b""

    def create_raise_exception_function(self, exception):
        def raise_exception(*args, **kwargs):
            raise exception
        return raise_exception

    @gen_test
    def test_socks_greeting(self):
        self.layer.socks_conn = Mock()
        self.layer.socks_conn.send = Mock(side_effect=self.collect_send_event)

        greeting_request = GreetingRequest((AUTH_TYPE["NO_AUTH"], ))
        yield self.layer.handle_greeting_request(
            greeting_request)

        self.assertIsNotNone(self.event)
        self.assertIsInstance(self.event, GreetingResponse)
        self.assertEqual(self.event.auth_type, AUTH_TYPE["NO_AUTH"])

    @gen_test
    def test_greeting_without_no_auth(self):
        self.layer.socks_conn = Mock()
        self.layer.socks_conn.send = Mock(side_effect=self.collect_send_event)

        yield self.layer.handle_greeting_request(GreetingRequest((AUTH_TYPE["GSSAPI"], )))

        self.assertIsNotNone(self.event)
        self.assertIsInstance(self.event, GreetingResponse)
        self.assertEqual(self.event.auth_type, AUTH_TYPE["NO_SUPPORT_AUTH_METHOD"])

    @gen_test
    def test_greeting_with_no_auth(self):
        self.layer.socks_conn = Mock()
        self.layer.socks_conn.send = Mock(side_effect=self.collect_send_event)

        yield self.layer.handle_greeting_request(
            GreetingRequest((AUTH_TYPE["NO_AUTH"], AUTH_TYPE["GSSAPI"])))

        self.assertIsNotNone(self.event)
        self.assertIsInstance(self.event, GreetingResponse)
        self.assertEqual(self.event.auth_type, AUTH_TYPE["NO_AUTH"])

    @gen_test
    def test_greeting_with_wrong_socks_version(self):
        # TODO: Currently, socks5 cannot support socks version 4
        # So it would failed when trying initiate Reuqest with version 4
        # And cannot test the behaivor of socks layer
        # It should be added in the future
        pass

    @gen_test
    def test_socks_request_ipv4(self):
        self.layer.socks_conn = Mock()
        self.layer.socks_conn.send = Mock(side_effect=self.collect_send_event)

        addr_future = self.layer.handle_request_and_create_destination(
            Request(REQ_COMMAND["CONNECT"], ADDR_TYPE["IPV4"],
                    u"127.0.0.1", self.port))

        dest_stream, host, port = yield addr_future

        self.assertIsNotNone(self.event)
        self.assertIsInstance(self.event, Response)
        self.assertEqual(self.event.status, RESP_STATUS["SUCCESS"])
        self.assertEqual(self.event.atyp, ADDR_TYPE["IPV4"])

        self.assertIsNotNone(dest_stream)
        self.assertFalse(dest_stream.closed())
        self.assertEqual(host, IPv4Address(u"127.0.0.1"))
        self.assertEqual(port, self.port)

        dest_stream.close()

    @gen_test
    def test_socks_request_remote_dns(self):
        self.layer.socks_conn = Mock()
        self.layer.socks_conn.send = Mock(side_effect=self.collect_send_event)

        addr_future = self.layer.handle_request_and_create_destination(
            Request(REQ_COMMAND["CONNECT"], ADDR_TYPE["DOMAINNAME"],
                    u"localhost", self.port))

        dest_stream, host, port = yield addr_future

        self.assertIsNotNone(self.event)
        self.assertIsInstance(self.event, Response)
        self.assertEqual(self.event.status, RESP_STATUS["SUCCESS"])
        self.assertEqual(self.event.atyp, ADDR_TYPE["DOMAINNAME"])

        self.assertIsNotNone(dest_stream)
        self.assertFalse(dest_stream.closed())
        self.assertEqual(host, "localhost")
        self.assertEqual(port, self.port)

        dest_stream.close()

    @gen_test
    def test_request_with_wrong_socks_command(self):
        self.layer.socks_conn = Mock()
        self.layer.socks_conn.send = Mock(side_effect=self.collect_send_event)

        addr_future = self.layer.handle_request_and_create_destination(
            Request(REQ_COMMAND["BIND"], ADDR_TYPE["DOMAINNAME"],
                    u"localhost", self.port))

        with self.assertRaises(ProtocolError):
            yield addr_future

        self.assertIsNotNone(self.event)
        self.assertIsInstance(self.event, Response)
        self.assertEqual(self.event.status, RESP_STATUS["COMMAND_NOT_SUPPORTED"])
        self.assertEqual(self.event.atyp, ADDR_TYPE["DOMAINNAME"])
        self.assertEqual(self.event.addr, "localhost")
        self.assertEqual(self.event.port, self.port)

    @gen_test
    def test_handle_connection_timeout(self):
        self.layer.socks_conn = Mock()
        self.layer.socks_conn.send = Mock(side_effect=self.collect_send_event)

        socks_request = Request(
            REQ_COMMAND["CONNECT"], ADDR_TYPE["IPV4"],
            u"1.2.3.4", self.port)

        self.layer.create_dest_stream = Mock(
            side_effect=self.create_raise_exception_function(TimeoutError))
        addr_future = self.layer.handle_request_and_create_destination(
            socks_request)

        with self.assertRaises(DestNotConnectedError):
            yield addr_future

        self.assertIsNotNone(self.event)
        self.assertIsInstance(self.event, Response)
        self.assertEqual(self.event.status, RESP_STATUS["NETWORK_UNREACHABLE"])
        self.assertEqual(self.event.atyp, ADDR_TYPE["IPV4"])
        self.assertEqual(self.event.addr, IPv4Address(u"1.2.3.4"))
        self.assertEqual(self.event.port, self.port)

    @gen_test
    def test_handle_stream_closed(self):
        self.layer.socks_conn = Mock()
        self.layer.socks_conn.send = Mock(side_effect=self.collect_send_event)

        socks_request = Request(
            REQ_COMMAND["CONNECT"], ADDR_TYPE["IPV4"],
            u"1.2.3.4", self.port)

        addr_not_support_status = RESP_STATUS["ADDRESS_TYPE_NOT_SUPPORTED"]
        network_unreach_status = RESP_STATUS["NETWORK_UNREACHABLE"]
        general_fail_status = RESP_STATUS["GENRAL_FAILURE"]

        error_cases = [
            (errno.ENOEXEC, addr_not_support_status),
            (errno.EBADF, addr_not_support_status),
            (errno.ETIMEDOUT, network_unreach_status),
            (errno.EADDRINUSE, general_fail_status),
            (55566, general_fail_status)]

        for code, expect_status in error_cases:
            self.layer.create_dest_stream = Mock(
                side_effect=self.create_raise_exception_function(
                    StreamClosedError((code, ))))
            result_future = self.layer.handle_request_and_create_destination(
                socks_request)
            with self.assertRaises(DestNotConnectedError):
                yield result_future

            self.assertIsNotNone(self.event)
            self.assertIsInstance(self.event, Response)
            self.assertEqual(self.event.status, expect_status)
            self.assertEqual(self.event.atyp, ADDR_TYPE["IPV4"])
            self.assertEqual(str(self.event.addr), "1.2.3.4")
            self.assertEqual(self.event.port, self.port)

    @gen_test
    def test_send_event_to_src_conn(self):
        self.layer.socks_conn = Mock()
        self.layer.socks_conn.send = Mock(return_value=b"ddddd")

        greeting_request = GreetingRequest((AUTH_TYPE["NO_AUTH"], ))

        yield self.layer.send_event_to_src_conn(greeting_request)
        data = yield self.client_stream.read_bytes(5)

        self.assertEqual(data, b"ddddd")
        self.layer.socks_conn.send.assert_called_with(greeting_request)

    @gen_test
    def test_send_event_to_src_conn_failed(self):
        self.layer.socks_conn = Mock()
        self.layer.socks_conn.send = Mock(side_effect=ValueError)

        greeting_request = GreetingRequest((AUTH_TYPE["NO_AUTH"], ))

        with self.assertRaises(ValueError):
            yield self.layer.send_event_to_src_conn(greeting_request)

    @gen_test
    def test_process_and_return_context(self):
        client_socks_conn = Connection(our_role="client")
        client_socks_conn.initiate_connection()
        result_future = self.layer.process_and_return_context()
        data = client_socks_conn.send(GreetingRequest([AUTH_TYPE["NO_AUTH"]]))

        yield self.client_stream.write(data)
        data = yield self.client_stream.read_bytes(1024, partial=True)
        event = client_socks_conn.recv(data)

        self.assertIsInstance(event, GreetingResponse)
        self.assertTrue(result_future.running())

        data = client_socks_conn.send(Request(
            REQ_COMMAND["CONNECT"], ADDR_TYPE["DOMAINNAME"],
            u"localhost", self.port))
        yield self.client_stream.write(data)

        data = yield self.client_stream.read_bytes(1024, partial=True)
        event = client_socks_conn.recv(data)

        self.assertIsInstance(event, Response)
        self.assertTrue(result_future.done())
        context = yield result_future
        self.assertEqual(context.host, "localhost")
        self.assertEqual(context.port, self.port)
        self.assertIsNotNone(context.dest_stream)

    @gen_test
    def test_process_with_src_stream_closed(self):
        result_future = self.layer.process_and_return_context()
        self.client_stream.close()
        with self.assertRaises(SrcStreamClosedError):
            yield result_future

    def tearDown(self):
        self.client_stream.close()
        self.src_stream.close()
