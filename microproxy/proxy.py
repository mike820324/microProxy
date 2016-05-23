from tornado import tcpserver
from tornado import gen
from tornado import concurrent
from tornado import iostream

from context import Context
from layer import SocksLayer, TransparentLayer, Http1Layer, ForwardLayer, TlsLayer

from utils import curr_loop, get_logger
from interceptor import MsgPublisherInterceptor as Interceptor
from exception import DestStreamClosedError, SrcStreamClosedError

logger = get_logger(__name__)


class LayerManager(object):
    def start_layer(self, context):
        mode = context.config["mode"]
        if mode == "socks":
            return SocksLayer(context)
        elif mode == "transparent":
            return TransparentLayer(context)
        else:
            # fixme: due to fail fast, need raise exception here
            logger.warning("Unsupport proxy mode : {0}".format(mode))

    def next_layer(self, current_layer, context):
        try:
            http_ports = [80]
            http_ports.extend(context.config["http_port"])
            https_ports = [443]
            https_ports.extend(context.config["https_port"])
        except KeyError:
            pass

        if isinstance(current_layer, SocksLayer) or isinstance(current_layer, TransparentLayer):
            if context.port in http_ports:
                return Http1Layer(context)
            elif context.port in https_ports:
                return TlsLayer(context)
            else:
                return ForwardLayer(context)

        if isinstance(current_layer, TlsLayer):
            if context.port in https_ports:
                return Http1Layer(context)


class ProxyServer(tcpserver.TCPServer):
    def __init__(self, config, proxy_server_handler=None):
        super(ProxyServer, self).__init__()
        self.config = config
        self.host = config["host"]
        self.port = config["port"]
        self.interceptor = Interceptor(config=config)
        self.layer_manager = LayerManager()

    @gen.coroutine
    def handle_stream(self, stream, port):
        try:
            context = Context(src_stream=stream,
                              config=self.config,
                              layer_manager=self.layer_manager)

            process_result = self.layer_manager.start_layer(context).process()
            if isinstance(process_result, concurrent.Future):
                yield process_result
        except gen.TimeoutError:
            stream.close()
        except DestStreamClosedError:
            logger.error("destination stream closed unexceptedly")
            stream.close()
        except SrcStreamClosedError:
            logger.error("source stream closed unexceptedly")
        except iostream.StreamClosedError:
            logger.error("stream closed")
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
