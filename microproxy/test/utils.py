import socket

from tornado.testing import AsyncTestCase, bind_unused_port
from tornado.locks import Event
from tornado.netutil import add_accept_handler
from tornado.gen import coroutine, Return

from microproxy.tornado_ext.iostream import MicroProxyIOStream


class ProxyAsyncTestCase(AsyncTestCase):
    @coroutine
    def create_iostream_pair(self):
        _lock = Event()
        server_streams = []

        def accept_callback(conn, addr):
            server_stream = MicroProxyIOStream(conn)
            server_streams.append(server_stream)
            # self.addCleanup(server_stream.close)
            _lock.set()

        listener, port = bind_unused_port()
        add_accept_handler(listener, accept_callback)
        client_stream = MicroProxyIOStream(socket.socket())
        yield [client_stream.connect(('127.0.0.1', port)),
               _lock.wait()]
        self.io_loop.remove_handler(listener)
        listener.close()

        raise Return((client_stream, server_streams[0]))
