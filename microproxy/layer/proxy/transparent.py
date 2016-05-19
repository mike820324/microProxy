import platform
import socket
import struct

from tornado import gen

from base import ProxyLayer
from microproxy.context import Context


class TransparentLayer(ProxyLayer):
    SO_ORIGINAL_DST = 80

    def __init__(self, context):
        super(TransparentLayer, self).__init__(context)

    @gen.coroutine
    def _get_dest_addr(self, src_stream):
        # Currently, we only support Linux
        if platform.system() != "Linux":
            raise NotImplementedError

        sock_opt = src_stream.socket.getsockopt(socket.SOL_IP,
                                                self.SO_ORIGINAL_DST,
                                                16)

        _, port, a1, a2, a3, a4 = struct.unpack("!HHBBBBxxxxxxxx", sock_opt)
        address = "%d.%d.%d.%d" % (a1, a2, a3, a4)

        dest_stream = yield self.create_dest_stream(address, port)
        raise gen.Return((dest_stream, address, port))

    @gen.coroutine
    def process(self):
        src_stream = self.context.src_stream

        dest_stream, host, port = yield self._get_dest_addr(src_stream)
        context = Context(src_stream=self.context.src_stream,
                          dest_stream=dest_stream,
                          host=host,
                          port=port,
                          config=self.context.config,
                          interceptor=self.context.interceptor,
                          layer_manager=self.context.layer_manager)

        self.context.layer_manager.next_layer(self, context).process()
        raise gen.Return(context)
