import platform
import socket
import struct

from tornado import gen

import base


class TransparentProxyHandler(base.ProxyHandler):
    SO_ORIGINAL_DST = 80

    def __init__(self, context):
        super(TransparentProxyHandler, self).__init__()
        self.context = context

    def _get_dest_addr(self, src_stream):
        # Currently, we only support Linux
        if platform.system() != "Linux":
            raise NotImplementedError

        sock_opt = src_stream.socket.getsockopt(socket.SOL_IP,
                                                self.SO_ORIGINAL_DST,
                                                16)

        _, port, a1, a2, a3, a4 = struct.unpack("!HHBBBBxxxxxxxx", sock_opt)
        address = "%d.%d.%d.%d" % (a1, a2, a3, a4)
        return address, port

    @gen.coroutine
    def process(self):
        src_stream = self.context.src_stream
        raise gen.Return(self._get_dest_addr(src_stream))
