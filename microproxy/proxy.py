from tornado import gen

from microproxy.tornado_ext.tcpserver import TCPServer
from microproxy import layer_manager
from microproxy.context import LayerContext
from microproxy.utils import curr_loop, get_logger
from microproxy.interceptor import get_interceptor

logger = get_logger(__name__)


class ProxyServer(TCPServer):
    def __init__(self, config, **kwargs):
        super(ProxyServer, self).__init__(**kwargs)
        self.config = config
        self.layer_manager = layer_manager

    @gen.coroutine
    def handle_stream(self, stream):
        try:
            initial_context = LayerContext(
                src_stream=stream,
                config=self.config,
                interceptor=get_interceptor())

            logger.debug("Start new layer manager")
            initial_layer = self.layer_manager.get_first_layer(initial_context)
            yield self.layer_manager.run_layers(initial_layer, initial_context)
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
