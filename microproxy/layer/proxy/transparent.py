import platform
import socket
import struct
from copy import copy

from tornado import gen
from tornado import concurrent

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
        new_context = copy(self.context)
        new_context.dest_stream = dest_stream
        new_context.host = host
        new_context.port = port

        try:
            process_result = self.context.layer_manager.next_layer(self, new_context).process()
            if isinstance(process_result, concurrent.Future):
                yield process_result
            raise gen.Return(None)
        finally:
            try:
                dest_stream.close()
            except:
                pass
