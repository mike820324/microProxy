import unittest
import sys
from mock import Mock

from tornado import gen, iostream
from microproxy import layer_manager
from microproxy.cert import init_cert_store
from microproxy.context import LayerContext
from microproxy.layer import SocksLayer, TransparentLayer, ReplayLayer
from microproxy.layer import TlsLayer, Http1Layer, Http2Layer, ForwardLayer
from microproxy.exception import DestStreamClosedError, SrcStreamClosedError, DestNotConnectedError


class TestLayerManager(unittest.TestCase):
    def setUp(self):
        super(TestLayerManager, self).setUp()
        self.config = {
            "mode": "socks",
            "http_port": [],
            "https_port": [],
            "certfile": "microproxy/test/test.crt",
            "keyfile": "microproxy/test/test.key"
        }
        init_cert_store(self.config)
        self.src_stream = Mock()

    def test_get_socks_layer(self):
        context = LayerContext(config=self.config, port=443)

        layer = layer_manager.get_first_layer(context)
        self.assertIsInstance(layer, SocksLayer)

    @unittest.skipIf('linux' not in sys.platform, "TransparentLayer only in linux")
    def test_get_transparent_layer_linux(self):
        config = self.config
        config["mode"] = "transparent"

        context = LayerContext(config=config, port=443)
        layer = layer_manager.get_first_layer(context)
        self.assertIsInstance(layer, TransparentLayer)

    @unittest.skipIf('linux' in sys.platform, "TransparentLayer only in linux")
    def test_get_transparent_layer_non_linux(self):
        config = self.config
        config["mode"] = "transparent"

        context = LayerContext(config=config, port=443)
        with self.assertRaises(NotImplementedError):
            layer_manager.get_first_layer(context)

    def test_get_replay_layer(self):
        config = self.config
        config["mode"] = "replay"

        context = LayerContext(config=config, port=443)
        layer = layer_manager.get_first_layer(context)
        self.assertIsInstance(layer, ReplayLayer)

    def test_get_layer_error(self):
        config = self.config
        config["mode"] = "test"

        context = LayerContext(config=config)
        with self.assertRaises(ValueError):
            layer_manager.get_first_layer(context)

    def test_get_tls_layer_from_socks(self):
        context = LayerContext(config=self.config, port=443)

        socks_layer = SocksLayer(context)
        layer = layer_manager._next_layer(socks_layer, context)
        self.assertIsInstance(layer, TlsLayer)

    @unittest.skipIf('linux' not in sys.platform, "TransparentLayer only in linux")
    def test_get_tls_layer_from_transparent(self):
        context = LayerContext(config=self.config, port=443)
        transparent_layer = TransparentLayer(context)
        layer = layer_manager._next_layer(transparent_layer, context)
        self.assertIsInstance(layer, TlsLayer)

    def test_get_http1_layer_from_socks_replay(self):
        context = LayerContext(config=self.config, port=80)

        socks_layer = SocksLayer(context)
        layer = layer_manager._next_layer(socks_layer, context)
        self.assertIsInstance(layer, Http1Layer)

        context.scheme = "http"
        replay_layer = ReplayLayer(context)
        layer = layer_manager._next_layer(replay_layer, context)
        self.assertIsInstance(layer, Http1Layer)

        context.scheme = "https"
        tls_layer = TlsLayer(context)
        layer = layer_manager._next_layer(tls_layer, context)
        self.assertIsInstance(layer, Http1Layer)

    @unittest.skipIf('linux' not in sys.platform, "TransparentLayer only in linux")
    def test_get_http1_layer_from_transparent(self):
        context = LayerContext(config=self.config, port=80)
        transparent_layer = TransparentLayer(context)
        layer = layer_manager._next_layer(transparent_layer, context)
        self.assertIsInstance(layer, Http1Layer)

    def test_get_http2_layer(self):
        context = LayerContext(config=self.config, port=443, scheme="h2")

        replay_layer = ReplayLayer(context)
        layer = layer_manager._next_layer(replay_layer, context)
        self.assertIsInstance(layer, Http2Layer)

        tls_layer = TlsLayer(context)
        layer = layer_manager._next_layer(tls_layer, context)
        self.assertIsInstance(layer, Http2Layer)

    def test_get_forward_layer_from_socks_replay(self):
        context = LayerContext(config=self.config, port=5555)

        socks_layer = SocksLayer(context)
        layer = layer_manager._next_layer(socks_layer, context)
        self.assertIsInstance(layer, ForwardLayer)

        context.scheme = "test"
        replay_layer = ReplayLayer(context)
        layer = layer_manager._next_layer(replay_layer, context)
        self.assertIsInstance(layer, ForwardLayer)

        context.scheme = "test"
        tls_layer = TlsLayer(context)
        layer = layer_manager._next_layer(tls_layer, context)
        self.assertIsInstance(layer, ForwardLayer)

    @unittest.skipIf('linux' not in sys.platform, "TransparentLayer only in linux")
    def test_get_forward_layer_from_transparent(self):
        context = LayerContext(config=self.config, port=5555)
        transparent_layer = TransparentLayer(context)
        layer = layer_manager._next_layer(transparent_layer, context)
        self.assertIsInstance(layer, ForwardLayer)

    def test_handle_layer_error(self):
        context = LayerContext(
            src_stream=Mock(), config=self.config, port=443, scheme="h2")

        layer_manager._handle_layer_error(gen.TimeoutError("timeout"), context)
        context.src_stream.close.assert_called_once_with()

        context = LayerContext(
            src_stream=Mock(), config=self.config, port=443, scheme="h2")
        layer_manager._handle_layer_error(DestNotConnectedError("stream closed"), context)
        context.src_stream.close.assert_not_called()

        context = LayerContext(
            src_stream=Mock(), config=self.config, port=443, scheme="h2")
        layer_manager._handle_layer_error(DestStreamClosedError("stream closed"), context)
        context.src_stream.close.assert_called_once_with()

        context = LayerContext(
            src_stream=Mock(), config=self.config, port=443, scheme="h2")
        layer_manager._handle_layer_error(SrcStreamClosedError("stream closed"), context)
        context.src_stream.close.assert_not_called()

        context = LayerContext(
            src_stream=Mock(), config=self.config, port=443, scheme="h2")
        layer_manager._handle_layer_error(iostream.StreamClosedError("stream closed"), context)
        context.src_stream.close.assert_called_once_with()

        context = LayerContext(
            src_stream=Mock(), config=self.config, port=443, scheme="h2")
        with self.assertRaises(ValueError):
            layer_manager._handle_layer_error(ValueError("stream closed"), context)
        context.src_stream.close.assert_not_called()
