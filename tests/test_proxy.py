from mock import Mock

from tornado.testing import AsyncTestCase

from microproxy.proxy import LayerManager
from microproxy.context import Context
from microproxy.layer import SocksLayer, TransparentLayer, Http1Layer, TlsLayer, NonTlsLayer


class LayerManagerTest(AsyncTestCase):
    def setUp(self):
        super(LayerManagerTest, self).setUp()
        self.config = {
            "mode": "socks",
            "http_port": [],
            "https_port": [],
            "certfile": None,
            "keyfile": None
        }
        self.layer_manager = LayerManager(config=self.config)
        self.src_stream = Mock()

    def test_get_tls_layer(self):
        context = Context(src_stream=Mock(),
                          config=self.config,
                          port=443)

        socks_layer = SocksLayer(context)
        layer = self.layer_manager.next_layer(socks_layer, context)
        assert isinstance(layer, TlsLayer)

        transparent_layer = TransparentLayer(context)
        layer = self.layer_manager.next_layer(transparent_layer, context)
        assert isinstance(layer, TlsLayer)

    def test_get_nontls_layer(self):
        context = Context(src_stream=Mock(),
                          config=self.config,
                          port=80)

        socks_layer = SocksLayer(context)
        layer = self.layer_manager.next_layer(socks_layer, context)
        assert isinstance(layer, NonTlsLayer)

        transparent_layer = TransparentLayer(context)
        layer = self.layer_manager.next_layer(transparent_layer, context)
        assert isinstance(layer, NonTlsLayer)

    def test_get_http1_layer(self):
        context = Context(src_stream=Mock(),
                          config=self.config,
                          port=80)

        context.scheme = "http"
        nontls_layer = NonTlsLayer(context)
        layer = self.layer_manager.next_layer(nontls_layer,
                                              context)
        assert isinstance(layer, Http1Layer)

        context.scheme = "https"
        tls_layer = TlsLayer(context)
        layer = self.layer_manager.next_layer(tls_layer, context)
        assert isinstance(layer, Http1Layer)
