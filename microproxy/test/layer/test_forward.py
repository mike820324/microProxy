from tornado.testing import gen_test

from microproxy.test.utils import ProxyAsyncTestCase
from microproxy.context import LayerContext
from microproxy.layer import ForwardLayer


class TestForwardLayer(ProxyAsyncTestCase):
    def setUp(self):
        super(TestForwardLayer, self).setUp()
        self.asyncSetUp()

    @gen_test
    def asyncSetUp(self):
        self.client_stream, src_stream = yield self.create_iostream_pair()
        dest_stream, self.server_stream = yield self.create_iostream_pair()
        self.context = LayerContext(mode="socks",
                                    src_stream=src_stream,
                                    dest_stream=dest_stream)

        self.forward_layer = ForwardLayer(dict(), self.context)

    @gen_test
    def test_forward_message(self):
        self.forward_layer.process_and_return_context()
        self.client_stream.write(b"aaa\r\n")
        message = yield self.server_stream.read_until(b"\r\n")
        assert message == b"aaa\r\n"

        self.server_stream.write(b"bbb\r\n")
        message = yield self.client_stream.read_until(b"\r\n")
        assert message == b"bbb\r\n"

        self.client_stream.close()
        self.server_stream.close()
        self.context.src_stream.close()
        self.context.dest_stream.close()
