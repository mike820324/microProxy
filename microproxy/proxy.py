from tornado import tcpserver
from tornado import gen
from tornado import iostream

from microproxy.context import LayerContext
from microproxy.layer import SocksLayer, TransparentLayer, ReplayLayer
from microproxy.layer import ForwardLayer, TlsLayer, Http1Layer, Http2Layer
from microproxy.iostream import MicroProxyIOStream
from microproxy.utils import curr_loop, get_logger
from microproxy.interceptor import Interceptor
from microproxy.exception import DestStreamClosedError, SrcStreamClosedError, DestNotConnectedError
from microproxy.cert import CertStore
from microproxy.event import EventManager

logger = get_logger(__name__)


class LayerManager(object):
    def __init__(self, config):
        self.config = config
        self.cert_store = CertStore(config)

    @gen.coroutine
    def run_layers(self, initial_layer_context):
        current_layer = self.get_first_layer(initial_layer_context)
        src_stream = initial_layer_context.src_stream

        while current_layer:
            try:
                logger.debug("Enter {0} Layer".format(current_layer))
                current_context = yield current_layer.process_and_return_context()
                logger.debug("Leave {0} Layer".format(current_layer))
                current_layer = self.next_layer(current_layer, current_context)
            except gen.TimeoutError:
                src_stream.close()
                break
            except DestNotConnectedError:
                logger.debug("destination not conected")
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
        mode = context.config["mode"]
        if mode == "socks":
            return SocksLayer(context)
        elif mode == "transparent":
            return TransparentLayer(context)
        elif mode == "replay":
            return ReplayLayer(context)
        else:
            raise ValueError("Unsupport proxy mode: {0}".format(mode))

    def next_layer(self, current_layer, context):
        http_ports = [80] + context.config["http_port"]
        https_ports = [443] + context.config["https_port"]

        if isinstance(current_layer, (SocksLayer, TransparentLayer)):
            if context.port in http_ports:
                context.scheme = "http"
                return Http1Layer(context)
            elif context.port in https_ports:
                return TlsLayer(context, self.cert_store)
            else:
                return ForwardLayer(context)

        if isinstance(current_layer, TlsLayer):
            if context.scheme == "https":
                return Http1Layer(context)
            elif context.scheme == "h2":
                return Http2Layer(context)
            else:
                return ForwardLayer(context)

        if isinstance(current_layer, ReplayLayer):
            if context.scheme in ("http", "https"):
                return Http1Layer(context)
            elif context.scheme == "h2":
                return Http2Layer(context)
            else:
                return ForwardLayer(context)


class ProxyServer(tcpserver.TCPServer):
    def __init__(self, config, **kwargs):
        super(ProxyServer, self).__init__(**kwargs)
        self.config = config
        self.interceptor = Interceptor(config=config)
        self.layer_manager = LayerManager(config)
        self.event_manager = EventManager(config, self)

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
                interceptor=self.interceptor)

            logger.debug("Start new layer manager")
            yield self.layer_manager.run_layers(initial_context)
        except Exception as e:
            # NOTE: not handle exception, log it and close the stream
            logger.exception(e)
            stream.close()

    def start_listener(self):
        self.listen(self.config["port"], self.config["host"])
        logger.info(
            "proxy server is listening at {0}:{1}".format(self.config["host"],
                                                          self.config["port"]))


def start_proxy_server(config):
    io_loop = curr_loop()
    server = ProxyServer(config, io_loop=io_loop)
    server.start_listener()

    try:
        curr_loop().start()
    except KeyboardInterrupt:
        # TODO: gracefully stop everything
        logger.info("bye")
