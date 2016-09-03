import mock
from tornado.testing import AsyncTestCase, gen_test
from tornado.concurrent import Future

from microproxy.layer.proxy.transparent import TransparentLayer


class TestTransparentLayer(AsyncTestCase):
    def setUp(self):
        super(TestTransparentLayer, self).setUp()

        self.dest_stream = mock.Mock()
        self.create_dest_stream = mock.Mock(
            return_value=self._create_future(self.dest_stream))
        self.dest_addr_resolver = mock.Mock(return_value=("localhost", 8080))

        self.context = mock.Mock()
        self.context.host = "localhost"
        self.context.port = 8080

        self.layer = TransparentLayer(
            self.context, dest_addr_resolver=self.dest_addr_resolver,
            create_dest_stream=self.create_dest_stream)

    def _create_future(self, result):
        future = Future()
        future.set_result(result)
        return future

    @gen_test
    def test_run_layer_with_other(self):
        context = yield self.layer.process_and_return_context()

        self.assertIs(context.dest_stream, self.dest_stream)
        self.assertEqual(context.host, "localhost")
        self.assertEqual(context.port, 8080)
        self.create_dest_stream.assert_called_with(("localhost", 8080))
