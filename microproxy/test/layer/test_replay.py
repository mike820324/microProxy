import mock
from tornado.testing import AsyncTestCase, gen_test
from tornado.concurrent import Future

from microproxy.layer.proxy.replay import ReplayLayer


class TestReplayLayer(AsyncTestCase):
    def setUp(self):
        super(TestReplayLayer, self).setUp()

        self.proxy_layer = mock.Mock()
        self.mock_stream = mock.Mock()
        self.mock_stream.start_tls = mock.Mock(
            return_value=self._create_future(self.mock_stream.dest_stream))
        self.proxy_layer.create_dest_stream = mock.Mock(
            return_value=self._create_future(self.mock_stream))

        self.context = mock.Mock()
        self.context.host = "localhost"
        self.context.port = 8080

        self.layer = ReplayLayer(
            self.context, proxy_layer=self.proxy_layer)

    def _create_future(self, result):
        future = Future()
        future.set_result(result)
        return future

    @gen_test
    def test_run_layer_with_https(self):
        self.context.scheme = "https"
        context = yield self.layer.process_and_return_context()

        self.assertEqual(context.dest_stream, self.mock_stream.dest_stream)
        self.proxy_layer.create_dest_stream.assert_called_with(
            ("localhost", 8080))

    @gen_test
    def test_run_layer_with_h2(self):
        self.context.scheme = "h2"
        context = yield self.layer.process_and_return_context()

        self.assertEqual(context.dest_stream, self.mock_stream.dest_stream)
        self.proxy_layer.create_dest_stream.assert_called_with(
            ("localhost", 8080))

    @gen_test
    def test_run_layer_with_other(self):
        self.context.scheme = "http"
        context = yield self.layer.process_and_return_context()

        self.assertEqual(context.dest_stream, self.mock_stream)
        self.proxy_layer.create_dest_stream.assert_called_with(
            ("localhost", 8080))
