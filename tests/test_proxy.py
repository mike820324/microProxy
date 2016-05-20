from mock import Mock

from tornado.concurrent import Future
from tornado.testing import AsyncTestCase

from microproxy.proxy import LayerManager
from microproxy.context import Context
from microproxy.layer import SocksLayer, TransparentLayer, Http1Layer, ForwardLayer, TlsLayer


class LayerManagerTest(AsyncTestCase):
    def setUp(self):
        super(LayerManagerTest, self).setUp()

    def test_get_socks_layer(self):
        config = {
            "mode": "socks",
            "http_port": [],
            "https_port": [],
            "certfile": None,
            "keyfile": None
        }
        context = Context(src_stream=Mock(),
                          config=config)
        layer = LayerManager(config).next_layer(None, context)
        assert isinstance(layer, SocksLayer)

    def test_get_transparent_layer(self):
        config = {
            "mode": "transparent",
            "http_port": [],
            "https_port": [],
            "certfile": None,
            "keyfile": None
        }
        context = Context(src_stream=Mock(),
                          config=config)

        layer = LayerManager(config).next_layer(None, context)
        assert isinstance(layer, TransparentLayer)

    def test_get_tls_layer(self):
        config = {
            "mode": "socks",
            "http_port": [],
            "https_port": [],
            "certfile": None,
            "keyfile": None
        }
        context = Context(src_stream=Mock(),
                          config=config,
                          port=443)

        socks_layer = SocksLayer(context)
        layer = LayerManager(config).next_layer(socks_layer, context)
        assert isinstance(layer, TlsLayer)

        transparent_layer = TransparentLayer(context)
        layer = LayerManager(config).next_layer(transparent_layer, context)
        assert isinstance(layer, TlsLayer)

    def test_get_http1_layer(self):
        config = {
            "mode": "socks",
            "http_port": [],
            "https_port": [],
            "certfile": None,
            "keyfile": None
        }
        context = Context(src_stream=Mock(),
                          config=config,
                          port=80)

        socks_layer = SocksLayer(context)
        layer = LayerManager(config).next_layer(socks_layer, context)
        assert isinstance(layer, Http1Layer)

        transparent_layer = TransparentLayer(context)
        layer = LayerManager(config).next_layer(transparent_layer, context)
        assert isinstance(layer, Http1Layer)

        tls_layer = TlsLayer(context)
        layer = LayerManager(config).next_layer(tls_layer, context)
        assert layer is None

        context.port = 443
        layer = LayerManager(config).next_layer(tls_layer, context)
        assert isinstance(layer, Http1Layer)
