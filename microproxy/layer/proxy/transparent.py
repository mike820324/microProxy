import platform
import socket
import struct

from tornado import gen

from microproxy.layer.base import ProxyLayer


class TransparentLayer(ProxyLayer):
    SO_ORIGINAL_DST = 80

    def __init__(self, context, dest_addr_resolver=None, **kwargs):
        super(TransparentLayer, self).__init__(context, **kwargs)
        self.dest_addr_resolver = dest_addr_resolver or self._get_dest_addr_resolver()

    def _get_dest_addr_resolver(self):  # pragma: no cover
        if platform.system() == "Linux":
            return self._linux_get_dest_addr
        else:
            raise NotImplementedError

    def _linux_get_dest_addr(self):  # pragma: no cover
        src_stream = self.context.src_stream
        sock_opt = src_stream.socket.getsockopt(socket.SOL_IP,
                                                self.SO_ORIGINAL_DST,
                                                16)
        _, port, a1, a2, a3, a4 = struct.unpack("!HHBBBBxxxxxxxx", sock_opt)
        address = "%d.%d.%d.%d" % (a1, a2, a3, a4)
        return (address, port)

    @gen.coroutine
    def process_and_return_context(self):
        host, port = self.dest_addr_resolver()
        dest_stream = yield self.create_dest_stream((host, port))
        self.context.dest_stream = dest_stream
        self.context.host = host
        self.context.port = port

        raise gen.Return(self.context)
