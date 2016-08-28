import socket

from tornado.testing import AsyncTestCase, gen_test, bind_unused_port
from tornado.locks import Event
from tornado.iostream import IOStream
from tornado.netutil import add_accept_handler

from microproxy.context import LayerContext
from microproxy.layer import SocksLayer
from microproxy.exception import ProtocolError

import socks5
from socks5 import GreetingRequest, Request
from socks5 import GreetingResponse, Response
from socks5 import RESP_STATUS, AUTH_TYPE, REQ_COMMAND, ADDR_TYPE


class SocksProxyHandlerTest(AsyncTestCase):
    def setUp(self):
        super(SocksProxyHandlerTest, self).setUp()
        self.asyncSetUp()

    @gen_test
    def asyncSetUp(self):
        listener, port = bind_unused_port()
        event = Event()

        def accept_callback(conn, addr):
            self.server_stream = IOStream(conn)
            self.addCleanup(self.server_stream.close)
            event.set()

        add_accept_handler(listener, accept_callback)
        self.client_stream = IOStream(socket.socket())
        self.addCleanup(self.client_stream.close)
        yield [self.client_stream.connect(('127.0.0.1', port)),
               event.wait()]
        self.io_loop.remove_handler(listener)
        listener.close()

        self.context = LayerContext(src_stream=self.server_stream)
        self.layer = SocksLayer(self.context)

        dest_listener, dest_port = bind_unused_port()
        self.listener = dest_listener
        self.port = dest_port

        def dest_accept_callback(conn, addr):
            self.dest_server_stream = IOStream(conn)
            self.addCleanup(self.dest_server_stream.close)
        add_accept_handler(dest_listener, dest_accept_callback)
        self.addCleanup(dest_listener.close)

    @gen_test
    def test_socks_greeting(self):
        greeting_request = GreetingRequest(
            socks5.VERSION, 1, (AUTH_TYPE["NO_AUTH"], ))
        greeting_response = self.layer.handle_greeting_request(
            greeting_request)

        self.client_stream.close()
        self.server_stream.close()

        self.assertIsInstance(greeting_response, GreetingResponse)
        self.assertEqual(greeting_response.version, socks5.VERSION)
        self.assertEqual(greeting_response.auth_type, AUTH_TYPE["NO_AUTH"])

    @gen_test
    def test_greeting_without_no_auth(self):
        greeting_request = GreetingRequest(
            socks5.VERSION, 1, (AUTH_TYPE["GSSAPI"], ))
        greeting_response = self.layer.handle_greeting_request(
            greeting_request)

        self.client_stream.close()
        self.server_stream.close()

        self.assertIsInstance(greeting_response, GreetingResponse)
        self.assertEqual(greeting_response.version, socks5.VERSION)
        self.assertEqual(
            greeting_response.auth_type, AUTH_TYPE["NO_SUPPORT_AUTH_METHOD"])

    @gen_test
    def test_greeting_with_auth(self):
        greeting_request = GreetingRequest(
            socks5.VERSION, 2, (AUTH_TYPE["NO_AUTH"], AUTH_TYPE["GSSAPI"]))
        greeting_response = self.layer.handle_greeting_request(
            greeting_request)

        self.client_stream.close()
        self.server_stream.close()

        self.assertIsInstance(greeting_response, GreetingResponse)
        self.assertEqual(greeting_response.version, socks5.VERSION)
        self.assertEqual(greeting_response.auth_type, AUTH_TYPE["NO_AUTH"])

    @gen_test
    def test_greeting_with_wrong_socks_version(self):
        greeting_request = GreetingRequest(
            4, 2, (AUTH_TYPE["NO_AUTH"], AUTH_TYPE["GSSAPI"]))
        greeting_response = self.layer.handle_greeting_request(
            greeting_request)

        self.client_stream.close()
        self.server_stream.close()

        self.assertIsInstance(greeting_response, GreetingResponse)
        self.assertEqual(greeting_response.version, socks5.VERSION)
        self.assertEqual(greeting_response.auth_type, AUTH_TYPE["NO_AUTH"])

    @gen_test
    def test_socks_request_ipv4(self):
        socks_request = Request(
            socks5.VERSION, REQ_COMMAND["CONNECT"], ADDR_TYPE["IPV4"],
            "127.0.0.1", self.port)
        addr_future = self.layer.handle_request(socks_request)

        error, event = yield addr_future
        self.client_stream.close()
        self.server_stream.close()

        self.assertIsNone(error)
        self.assertIsInstance(event, Response)
        self.assertEqual(event.status, RESP_STATUS["SUCCESS"])
        self.assertEqual(event.atyp, ADDR_TYPE["IPV4"])
        self.assertEqual(event.addr, "127.0.0.1")
        self.assertEqual(event.port, self.port)

    @gen_test
    def test_socks_request_remote_dns(self):
        socks_request = Request(
            socks5.VERSION, REQ_COMMAND["CONNECT"], ADDR_TYPE["DOMAINNAME"],
            "localhost", self.port)
        addr_future = self.layer.handle_request(socks_request)

        error, event = yield addr_future
        self.client_stream.close()
        self.server_stream.close()

        self.assertIsNone(error)
        self.assertIsInstance(event, Response)
        self.assertEqual(event.status, RESP_STATUS["SUCCESS"])
        self.assertEqual(event.atyp, ADDR_TYPE["DOMAINNAME"])
        self.assertEqual(event.addr, "localhost")
        self.assertEqual(event.port, self.port)

    # @gen_test
    # def test_request_with_wrong_socks_version(self):
    #     self.client_stream.write(struct.pack("!BBxB", 4, 1, 1))
    #     with self.assertRaises(ProtocolError):
    #         yield self.layer.socks_request()
    #     self.client_stream.close()
    #     self.server_stream.close()

    @gen_test
    def test_request_with_wrong_socks_command(self):
        socks_request = Request(
            socks5.VERSION, REQ_COMMAND["BIND"], ADDR_TYPE["DOMAINNAME"],
            "localhost", self.port)

        addr_future = self.layer.handle_request(socks_request)
        error, event = yield addr_future

        self.assertIsInstance(error, ProtocolError)
        self.assertIsInstance(event, Response)
        self.assertEqual(event.status, RESP_STATUS["COMMAND_NOT_SUPPORTED"])
        self.assertEqual(event.atyp, ADDR_TYPE["DOMAINNAME"])
        self.assertEqual(event.addr, "localhost")
        self.assertEqual(event.port, self.port)

        self.client_stream.close()
        self.server_stream.close()
