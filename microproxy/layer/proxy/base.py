import socket
import datetime

from tornado import gen
from tornado import iostream

from microproxy.utils import get_logger
logger = get_logger(__name__)


class ProxyLayer(object):
    def __init__(self, context):
        super(ProxyLayer, self).__init__()
        self.context = context

    def process(self):
        raise NotImplementedError

    @gen.coroutine
    def create_dest_stream(self, host, port):
        dest_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
        dest_stream = iostream.IOStream(dest_socket)
        try:
            yield gen.with_timeout(datetime.timedelta(5), dest_stream.connect((host, port)))
            raise gen.Return(dest_stream)
        except gen.TimeoutError:
            logger.warning("Connect to Destination Timeout")
            raise
