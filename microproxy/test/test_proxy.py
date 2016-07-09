from mock import Mock

from tornado.testing import AsyncTestCase

from microproxy.proxy import LayerManager
from microproxy.context import LayerContext
from microproxy.layer import SocksLayer, TransparentLayer, TlsLayer
from microproxy.layer import Http1Layer, Http2Layer


class LayerManagerTest(AsyncTestCase):
    def setUp(self):
        super(LayerManagerTest, self).setUp()
        self.config = {
            "mode": "socks",
            "http_port": [],
            "https_port": [],
            "certfile": "microproxy/test/test.crt",
            "keyfile": "microproxy/test/test.key"
        }
        self.layer_manager = LayerManager(config=self.config)
        self.src_stream = Mock()

    def test_get_socks_layer(self):
        context = LayerContext(src_stream=Mock(),
                               config=self.config,
                               port=443)

        layer = self.layer_manager.get_first_layer(context)
        self.assertIsInstance(layer, SocksLayer)

    def test_get_transparent_layer(self):
        context = LayerContext(src_stream=Mock(),
                               config=self.config,
                               port=443)

        config = self.config
        config["mode"] = "transparent"
        layer_manager = LayerManager(config=config)
        layer = layer_manager.get_first_layer(context)
        self.assertIsInstance(layer, TransparentLayer)

    def test_get_tls_layer(self):
        context = LayerContext(src_stream=Mock(),
                               config=self.config,
                               port=443)

        socks_layer = SocksLayer(context)
        layer = self.layer_manager.next_layer(socks_layer, context)
        self.assertIsInstance(layer, TlsLayer)

        transparent_layer = TransparentLayer(context)
        layer = self.layer_manager.next_layer(transparent_layer, context)
        self.assertIsInstance(layer, TlsLayer)

    def test_get_http1_layer(self):
        context = LayerContext(src_stream=Mock(),
                               config=self.config,
                               port=80)

        socks_layer = SocksLayer(context)
        layer = self.layer_manager.next_layer(socks_layer, context)
        self.assertIsInstance(layer, Http1Layer)

        transparent_layer = TransparentLayer(context)
        layer = self.layer_manager.next_layer(transparent_layer, context)
        self.assertIsInstance(layer, Http1Layer)

        context.scheme = "https"
        tls_layer = TlsLayer(context, None)
        layer = self.layer_manager.next_layer(tls_layer, context)
        self.assertIsInstance(layer, Http1Layer)

    def test_get_http2_layer(self):
        context = LayerContext(src_stream=Mock(),
                               config=self.config,
                               port=443)

        context.scheme = "h2"
        tls_layer = TlsLayer(context, None)
        layer = self.layer_manager.next_layer(tls_layer, context)
        self.assertIsInstance(layer, Http2Layer)
