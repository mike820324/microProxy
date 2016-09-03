import mock
from tornado.testing import AsyncTestCase, gen_test
from tornado.concurrent import Future

from microproxy.layer.proxy.replay import ReplayLayer


class TestReplayLayer(AsyncTestCase):
    def setUp(self):
        super(TestReplayLayer, self).setUp()

        self.streams = mock.Mock()
        self.create_dest_stream = mock.Mock(
            return_value=self._create_future(self.streams.dest_stream))
        self.streams.dest_stream.start_tls = mock.Mock(
            return_value=self._create_future(self.streams.tls_stream))

        self.context = mock.Mock()
        self.context.host = "localhost"
        self.context.port = 8080

    def _create_future(self, result):
        future = Future()
        future.set_result(result)
        return future

    @gen_test
    def test_run_layer_with_https(self):
        self.context.scheme = "https"
        self.layer = ReplayLayer(
            self.context, create_dest_stream=self.create_dest_stream)

        context = yield self.layer.process_and_return_context()

        self.assertIs(context.dest_stream, self.streams.tls_stream)
        self.create_dest_stream.assert_called_with(
            ("localhost", 8080))

    @gen_test
    def test_run_layer_with_h2(self):
        self.context.scheme = "h2"
        self.layer = ReplayLayer(
            self.context, create_dest_stream=self.create_dest_stream)

        context = yield self.layer.process_and_return_context()

        self.assertIs(context.dest_stream, self.streams.tls_stream)
        self.create_dest_stream.assert_called_with(
            ("localhost", 8080))

    @gen_test
    def test_run_layer_with_other(self):
        self.context.scheme = "http"
        self.layer = ReplayLayer(
            self.context, create_dest_stream=self.create_dest_stream)

        context = yield self.layer.process_and_return_context()

        self.assertIs(context.dest_stream, self.streams.dest_stream)
        self.create_dest_stream.assert_called_with(
            ("localhost", 8080))
