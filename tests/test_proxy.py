from mock import Mock

from tornado.concurrent import Future
from tornado.testing import AsyncTestCase

from microproxy.proxy import ProxyServerHandler
from microproxy.mode import SocksProxyHandler, TransparentProxyHandler


class ProxyServerHandlerTest(AsyncTestCase):
    def setUp(self):
        super(ProxyServerHandlerTest, self).setUp()

    def test_get_proxy_handler_socks(self):
        config = {
            "mode": "socks",
            "http_port": [],
            "https_port": []
        }
        proxy_handler = ProxyServerHandler(config, interceptor=Mock()).get_proxy_handler()
        assert isinstance(proxy_handler, SocksProxyHandler)

    def test_get_proxy_handler_transparent(self):
        config = {
            "mode": "transparent",
            "http_port": [],
            "https_port": []
        }
        proxy_handler = ProxyServerHandler(config, interceptor=Mock()).get_proxy_handler()
        assert isinstance(proxy_handler, TransparentProxyHandler)


def create_future(value):
    future = Future()
    future.set_result(value)
    return future
