from tornado import tcpserver
from tornado import gen
from tornado import iostream

from context import Context
from layer import SocksLayer, TransparentLayer, Http1Layer, ForwardLayer, TlsLayer, NonTlsLayer

from utils import curr_loop, get_logger
from interceptor import MsgPublisherInterceptor as Interceptor
from exception import DestStreamClosedError, SrcStreamClosedError

logger = get_logger(__name__)


class LayerManager(object):
    def __init__(self, src_stream, config):
        self.src_stream = src_stream
        self.config = config

    @gen.coroutine
    def start_layer(self):
        mode = self.config["mode"]
        if mode == "socks":
            layer_constructor = SocksLayer
        elif mode == "transparent":
            layer_constructor = TransparentLayer
        else:
            logger.error("Unsupport proxy mode : {0}".format(mode))
            raise ValueError

        current_context = Context(src_stream=self.src_stream,
                                  config=self.config)
        while True:
            try:
                current_layer = layer_constructor(current_context)
                logger.debug("Enter {0} Layer".format(current_layer))
                current_context = yield current_layer.process()
                logger.debug("Leave {0} Layer".format(current_layer))
                layer_constructor = self.next_layer(current_layer, current_context)

                if not layer_constructor:
                    logger.debug("Layer Loop Ended")
                    break
            except gen.TimeoutError:
                self.src_stream.close()
            except DestStreamClosedError:
                logger.error("destination stream closed unexceptedly")
                self.src_stream.close()
            except SrcStreamClosedError:
                logger.error("source stream closed unexceptedly")
            except iostream.StreamClosedError:
                logger.error("stream closed")
                self.src_stream.close()
            except Exception:
                raise

        raise gen.Return(None)

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
                return NonTlsLayer
            elif context.port in https_ports:
                return TlsLayer
            else:
                return ForwardLayer

        if isinstance(current_layer, TlsLayer) or isinstance(current_layer, NonTlsLayer):
            if context.schema == "http" or context.schema == "https":
                return Http1Layer
            elif context.schema == "h2":
                return ForwardLayer


class ProxyServer(tcpserver.TCPServer):
    def __init__(self, config, proxy_server_handler=None):
        super(ProxyServer, self).__init__()
        self.config = config
        self.host = config["host"]
        self.port = config["port"]
        self.interceptor = Interceptor(config=config)

    @gen.coroutine
    def handle_stream(self, stream, port):
        try:
            logger.debug("Start new layer manager")
            layer_manager = LayerManager(stream, self.config)
            yield layer_manager.start_layer()
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
