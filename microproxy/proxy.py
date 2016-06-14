from tornado import tcpserver
from tornado import gen
from tornado import iostream

from context import Context
from layer import SocksLayer, TransparentLayer, Http1Layer, ForwardLayer, TlsLayer, NonTlsLayer
from microproxy.iostream import MicroProxyIOStream

from utils import curr_loop, get_logger
from interceptor import Interceptor
from exception import DestStreamClosedError, SrcStreamClosedError

logger = get_logger(__name__)


class LayerManager(object):
    def __init__(self, config):
        self.config = config

    @gen.coroutine
    def run_layers(self, src_stream):
        current_context = Context(src_stream=src_stream,
                                  config=self.config)
        current_layer = self.get_first_layer(current_context)

        while current_layer:
            try:
                logger.debug("Enter {0} Layer".format(current_layer))
                current_context = yield current_layer.process_and_return_context()
                logger.debug("Leave {0} Layer".format(current_layer))
                current_layer = self.next_layer(current_layer, current_context)
            except gen.TimeoutError:
                src_stream.close()
                break
            except DestStreamClosedError:
                logger.error("destination stream closed unexceptedly")
                src_stream.close()
                break
            except SrcStreamClosedError:
                logger.error("source stream closed unexceptedly")
                break
            except iostream.StreamClosedError:
                logger.error("stream closed")
                src_stream.close()
                break
            except Exception:
                raise

        raise gen.Return(None)

    def get_first_layer(self, context):
        mode = self.config["mode"]
        if mode == "socks":
            return SocksLayer(context)
        elif mode == "transparent":
            return TransparentLayer(context)
        else:
            raise ValueError("Unsupport proxy mode: {0}".format(mode))

    def next_layer(self, current_layer, context):
        http_ports = [80]
        http_ports.extend(context.config["http_port"])
        https_ports = [443]
        https_ports.extend(context.config["https_port"])

        if isinstance(current_layer, SocksLayer) or isinstance(current_layer, TransparentLayer):
            if context.port in http_ports:
                return NonTlsLayer(context)
            elif context.port in https_ports:
                return TlsLayer(context)
            else:
                return ForwardLayer(context)

        if isinstance(current_layer, TlsLayer) or isinstance(current_layer, NonTlsLayer):
            if context.scheme == "http" or context.scheme == "https":
                return Http1Layer(context)
            elif context.scheme == "h2":
                return ForwardLayer(context)


class ProxyServer(tcpserver.TCPServer):
    def __init__(self, config, proxy_server_handler=None):
        super(ProxyServer, self).__init__()
        self.config = config
        self.host = config["host"]
        self.port = config["port"]
        self.interceptor = Interceptor(config=config)
        self.layer_manager = LayerManager(config)

    def _handle_connection(self, connection, address):
        try:
            stream = MicroProxyIOStream(connection,
                                        io_loop=self.io_loop,
                                        max_buffer_size=self.max_buffer_size,
                                        read_chunk_size=self.read_chunk_size)
            future = self.handle_stream(stream, address)
            if future is not None:
                self.io_loop.add_future(future, lambda f: f.result())
        except Exception as e:
            logger.exception(e)
            raise

    @gen.coroutine
    def handle_stream(self, stream, port):
        try:
            logger.debug("Start new layer manager")
            yield self.layer_manager.run_layers(stream)
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
