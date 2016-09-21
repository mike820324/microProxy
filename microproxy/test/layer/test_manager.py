import unittest
import sys
from mock import Mock

from tornado import gen, iostream
from microproxy import layer_manager
from microproxy.context import LayerContext, ServerContext
from microproxy.layer import SocksLayer, TransparentLayer, ReplayLayer
from microproxy.layer import TlsLayer, Http1Layer, Http2Layer, ForwardLayer
from microproxy.exception import DestStreamClosedError, SrcStreamClosedError, DestNotConnectedError


class TestLayerManager(unittest.TestCase):
    def setUp(self):
        super(TestLayerManager, self).setUp()
        config = {
            "mode": "socks",
            "http_port": [],
            "https_port": [],
            "certfile": "microproxy/test/test.crt",
            "keyfile": "microproxy/test/test.key"
        }
        self.server_state = ServerContext(config=config)
        self.src_stream = Mock()

    def test_get_socks_layer(self):
        context = LayerContext(mode="socks", port=443)

        layer = layer_manager.get_first_layer(context)
        self.assertIsInstance(layer, SocksLayer)

    @unittest.skipIf('linux' not in sys.platform, "TransparentLayer only in linux")
    def test_get_transparent_layer_linux(self):
        context = LayerContext(mode="transparent", port=443)
        layer = layer_manager.get_first_layer(context)
        self.assertIsInstance(layer, TransparentLayer)

    @unittest.skipIf('linux' in sys.platform, "TransparentLayer only in linux")
    def test_get_transparent_layer_non_linux(self):
        context = LayerContext(mode="transparent", port=443)
        with self.assertRaises(NotImplementedError):
            layer_manager.get_first_layer(context)

    def test_get_replay_layer(self):
        context = LayerContext(mode="replay", port=443)
        layer = layer_manager.get_first_layer(context)
        self.assertIsInstance(layer, ReplayLayer)

    def test_get_tls_layer_from_socks(self):
        context = LayerContext(mode="socks", port=443)

        socks_layer = SocksLayer(context)
        layer = layer_manager._next_layer(self.server_state, socks_layer, context)
        self.assertIsInstance(layer, TlsLayer)

    @unittest.skipIf('linux' not in sys.platform, "TransparentLayer only in linux")
    def test_get_tls_layer_from_transparent(self):
        context = LayerContext(mode="socks", port=443)
        transparent_layer = TransparentLayer(context)
        layer = layer_manager._next_layer(self.server_state, transparent_layer, context)
        self.assertIsInstance(layer, TlsLayer)

    def test_get_http1_layer_from_socks_replay(self):
        context = LayerContext(mode="socks", port=80)

        socks_layer = SocksLayer(context)
        layer = layer_manager._next_layer(self.server_state, socks_layer, context)
        self.assertIsInstance(layer, Http1Layer)

        context.scheme = "http"
        replay_layer = ReplayLayer(context)
        layer = layer_manager._next_layer(self.server_state, replay_layer, context)
        self.assertIsInstance(layer, Http1Layer)

        context.scheme = "https"
        tls_layer = TlsLayer(self.server_state, context)
        layer = layer_manager._next_layer(self.server_state, tls_layer, context)
        self.assertIsInstance(layer, Http1Layer)

    @unittest.skipIf('linux' not in sys.platform, "TransparentLayer only in linux")
    def test_get_http1_layer_from_transparent(self):
        context = LayerContext(mode="socks", port=80)
        transparent_layer = TransparentLayer(context)
        layer = layer_manager._next_layer(self.server_state, transparent_layer, context)
        self.assertIsInstance(layer, Http1Layer)

    def test_get_http2_layer(self):
        context = LayerContext(mode="socks", port=443, scheme="h2")

        replay_layer = ReplayLayer(context)
        layer = layer_manager._next_layer(self.server_state, replay_layer, context)
        self.assertIsInstance(layer, Http2Layer)

        tls_layer = TlsLayer(self.server_state, context)
        layer = layer_manager._next_layer(self.server_state, tls_layer, context)
        self.assertIsInstance(layer, Http2Layer)

    def test_get_forward_layer_from_socks_replay(self):
        context = LayerContext(mode="socks", port=5555)

        socks_layer = SocksLayer(context)
        layer = layer_manager._next_layer(self.server_state, socks_layer, context)
        self.assertIsInstance(layer, ForwardLayer)

        context.scheme = "test"
        replay_layer = ReplayLayer(context)
        layer = layer_manager._next_layer(self.server_state, replay_layer, context)
        self.assertIsInstance(layer, ForwardLayer)

        context.scheme = "test"
        tls_layer = TlsLayer(self.server_state, context)
        layer = layer_manager._next_layer(self.server_state, tls_layer, context)
        self.assertIsInstance(layer, ForwardLayer)

    def test_get_forward_layer_from_transparent(self):
        context = LayerContext(mode="socks", port=5555)
        transparent_layer = TransparentLayer(context)
        layer = layer_manager._next_layer(self.server_state, transparent_layer, context)
        self.assertIsInstance(layer, ForwardLayer)

    def test_handle_layer_error(self):
        context = LayerContext(
            mode="socks", src_stream=self.src_stream, port=443, scheme="h2")

        layer_manager._handle_layer_error(gen.TimeoutError("timeout"), context)
        context.src_stream.close.assert_called_once_with()

        context.src_stream.reset_mock()
        layer_manager._handle_layer_error(DestNotConnectedError("stream closed"), context)
        context.src_stream.close.assert_not_called()

        context.src_stream.reset_mock()
        layer_manager._handle_layer_error(DestStreamClosedError("stream closed"), context)
        context.src_stream.close.assert_called_once_with()

        context.src_stream.reset_mock()
        layer_manager._handle_layer_error(SrcStreamClosedError("stream closed"), context)
        context.src_stream.close.assert_not_called()

        context.src_stream.reset_mock()
        layer_manager._handle_layer_error(iostream.StreamClosedError("stream closed"), context)
        context.src_stream.close.assert_called_once_with()

    def test_handle_unhandled_layer_error(self):
        context = LayerContext(
            mode="socks", src_stream=Mock(), port=443, scheme="h2")
        try:
            raise ValueError("stream closed")
        except ValueError as e:
            with self.assertRaises(ValueError):
                layer_manager._handle_layer_error(e, context)
        context.src_stream.close.assert_not_called()
