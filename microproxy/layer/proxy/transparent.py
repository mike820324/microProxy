import platform
import socket
import struct

from tornado import gen

from base import ProxyLayer


class TransparentLayer(ProxyLayer):
    SO_ORIGINAL_DST = 80

    def __init__(self, context):
        super(TransparentLayer, self).__init__(context)

    def _get_dest_addr(self):
        src_stream = self.context.src_stream
        # Currently, we only support Linux
        if platform.system() != "Linux":
            raise NotImplementedError

        sock_opt = src_stream.socket.getsockopt(socket.SOL_IP,
                                                self.SO_ORIGINAL_DST,
                                                16)

        _, port, a1, a2, a3, a4 = struct.unpack("!HHBBBBxxxxxxxx", sock_opt)
        address = "%d.%d.%d.%d" % (a1, a2, a3, a4)
        return (address, port)

    @gen.coroutine
    def process(self):
        host, port = self._get_dest_addr()
        dest_stream = yield self.create_dest_stream((host, port))
        self.context.dest_stream = dest_stream
        self.context.host = host
        self.context.port = port

        raise gen.Return(self.context)
