from tornado import gen

from microproxy.layer.base import ProxyLayer


class HttpProxyLayer(ProxyLayer):  # pragma: no cover
    def __init__(self, context, dest_addr_resolver=None, **kwargs):
        super(HttpProxyLayer, self).__init__(context, **kwargs)

    @gen.coroutine
    def process_and_return_context(self):
        raise gen.Return(self.context)
