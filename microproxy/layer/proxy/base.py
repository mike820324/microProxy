import socket
from copy import copy
from tornado import gen

from microproxy import iostream


class ProxyLayer(object):
    def __init__(self, context):
        super(ProxyLayer, self).__init__()
        self.context = copy(context)

    def process_and_return_context(self):
        raise NotImplementedError

    @gen.coroutine
    def create_dest_stream(self, dest_addr_info):
        dest_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
        dest_stream = iostream.MicroProxyIOStream(dest_socket)
        yield gen.with_timeout(5, dest_stream.connect(dest_addr_info))
        raise gen.Return(dest_stream)
