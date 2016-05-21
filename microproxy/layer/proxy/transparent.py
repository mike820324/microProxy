import platform
import socket
import struct
from copy import copy

from tornado import gen

from base import ProxyLayer


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
        new_context = copy(self.context)
        new_context.dest_stream = dest_stream
        new_context.host = host
        new_context.port = port

        self.context.layer_manager.next_layer(self, new_context).process()
