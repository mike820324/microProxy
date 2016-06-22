import socket
from copy import copy


class ProxyLayer(object):
    def __init__(self, context):
        super(ProxyLayer, self).__init__()
        self.context = copy(context)

    def process_and_return_context(self):
        raise NotImplementedError

    def create_dest_stream(self, dest_addr_info):
        dest_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
        dest_socket.setblocking(True)
        # FIXME: using concurrent.futures ThreadExecutor?
        dest_socket.settimeout(3)
        dest_socket.connect(dest_addr_info)
        dest_socket.settimeout(None)
        return dest_socket
