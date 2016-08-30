from tornado import tcpserver
from tornado import gen

from microproxy.context import LayerContext
from microproxy.iostream import MicroProxyIOStream
from microproxy.utils import curr_loop, get_logger
from microproxy.interceptor import get_interceptor
from microproxy.layer_manager import run_layers

logger = get_logger(__name__)


class ProxyServer(tcpserver.TCPServer):
    def __init__(self, config, **kwargs):
        super(ProxyServer, self).__init__(**kwargs)
        self.config = config

    def _handle_connection(self, connection, address):
        try:
            stream = MicroProxyIOStream(connection,
                                        io_loop=self.io_loop,
                                        max_buffer_size=self.max_buffer_size,
                                        read_chunk_size=self.read_chunk_size)
            future = self.handle_stream(stream)
            if future is not None:
                self.io_loop.add_future(future, lambda f: f.result())
        except Exception as e:
            logger.exception(e)
            raise

    @gen.coroutine
    def handle_stream(self, stream):
        try:
            initial_context = LayerContext(
                src_stream=stream,
                config=self.config,
                interceptor=get_interceptor(self.config))

            logger.debug("Start new layer manager")
            yield run_layers(initial_context)
        except Exception as e:
            # NOTE: not handle exception, log it and close the stream
            logger.exception(e)
            stream.close()

    def start_listener(self):
        self.listen(self.config["port"], self.config["host"])
        logger.info(
            "proxy server is listening at {0}:{1}".format(self.config["host"],
                                                          self.config["port"]))


def start_tcp_server(config):
    io_loop = curr_loop()
    server = ProxyServer(config, io_loop=io_loop)
    server.start_listener()
