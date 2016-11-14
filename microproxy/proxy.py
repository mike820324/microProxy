from tornado import gen

from microproxy.tornado_ext.tcpserver import TCPServer
from microproxy.layer import manager as layer_manager
from microproxy.context import LayerContext
from microproxy.utils import curr_loop

from microproxy.log import ProxyLogger
logger = ProxyLogger.get_logger("ProxyServer")


class ProxyServer(TCPServer):
    def __init__(self, server_state, **kwargs):
        super(ProxyServer, self).__init__(**kwargs)
        self.server_state = server_state
        self.config = server_state.config

    @gen.coroutine
    def handle_stream(self, stream):
        try:
            initial_context = LayerContext(
                mode=self.config["mode"], src_stream=stream)

            logger.debug("Start new layer manager")
            initial_layer = layer_manager.get_first_layer(initial_context)
            yield layer_manager.run_layers(
                self.server_state, initial_layer, initial_context)
        except Exception as e:
            # NOTE: not handle exception, log it and close the stream
            logger.exception(e)
            stream.close()

    def start_listener(self):
        self.listen(self.config["port"], self.config["host"])
        logger.info(
            "proxy server is listening at {0}:{1}".format(self.config["host"],
                                                          self.config["port"]))


def start_tcp_server(server_state):
    io_loop = curr_loop()
    server = ProxyServer(server_state, io_loop=io_loop)
    server.start_listener()
