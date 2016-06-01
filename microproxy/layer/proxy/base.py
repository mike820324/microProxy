import socket
from copy import copy

from microproxy.utils import get_logger
logger = get_logger(__name__)


class ProxyLayer(object):
    def __init__(self, context):
        super(ProxyLayer, self).__init__()
        self.context = copy(context)

    def process(self):
        raise NotImplementedError

    def create_dest_stream(self, dest_addr_info):
        dest_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
        dest_socket.setblocking(True)
        try:
            dest_socket.connect(dest_addr_info)
            return dest_socket
        except:
            raise
