from tornado import tcpserver
from tornado import gen

from context import Context
from layer import SocksLayer, TransparentLayer, Http1Layer, ForwardLayer, TlsLayer

from utils import curr_loop, get_logger
from interceptor import MsgPublisherInterceptor as Interceptor

logger = get_logger(__name__)


class LayerManager(object):
    def __init__(self, config):
        super(LayerManager, self).__init__()
        try:
            self.http_ports = config["http_port"]
        except KeyError:
            self.http_ports = []
        try:
            self.https_ports = config["https_port"]
        except KeyError:
            self.http_ports = []

    def next_layer(self, current_layer, context):
        if current_layer is None:
            mode = context.config["mode"]
            if mode == "socks":
                return SocksLayer(context)
            elif mode == "transparent":
                return TransparentLayer(context)
            else:
                # fixme: due to fail fast, need raise exception here
                logger.warning("Unsupport proxy mode : {0}".format(mode))

        if isinstance(current_layer, SocksLayer) or isinstance(current_layer, TransparentLayer):
            if context.port == 80 or context.port in self.http_ports:
                return Http1Layer(context)
            elif context.port == 443 or context.port in self.https_ports:
                return TlsLayer(context)
            else:
                return ForwardLayer(context)

        if isinstance(current_layer, TlsLayer):
            if context.port == 443 or context.port in self.https_ports:
                return Http1Layer(context)


class ProxyServer(tcpserver.TCPServer):
    def __init__(self, config, proxy_server_handler=None):
        super(ProxyServer, self).__init__()
        self.config = config
        self.host = config["host"]
        self.port = config["port"]
        self.interceptor = Interceptor(config=config)
        self.layer_manager = LayerManager(self.config)

    @gen.coroutine
    def handle_stream(self, stream, port):
        try:
            context = Context(src_stream=stream,
                              interceptor=self.interceptor,
                              config=self.config,
                              layer_manager=self.layer_manager)

            self.layer_manager.next_layer(None, context).process()
        except gen.TimeoutError:
            stream.close()
        except Exception as e:
            # not handle exception, log it and close the stream
            logger.exception(e)
            stream.close()

    def start_listener(self):
        self.listen(self.port, self.host)
        logger.info("proxy server is listening at {0}:{1}".format(self.host, self.port))


def start_proxy_server(config):
    server = ProxyServer(config)
    server.start_listener()

    try:
        curr_loop().start()
    except KeyboardInterrupt:
        # fixme: gracefully stop everything
        logger.info("bye")
