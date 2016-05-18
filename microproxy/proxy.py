import socket
import ssl
import datetime

from tornado import tcpserver
from tornado import iostream
from tornado import gen

from mode import SocksProxyHandler, TransparentProxyHandler
from context import Context
from utils import curr_loop, get_logger
from layer import Http1Layer, ForwardLayer
from interceptor import MsgPublisherInterceptor as Interceptor

logger = get_logger(__name__)


class ProxyServer(tcpserver.TCPServer):
    def __init__(self, config, proxy_server_handler=None):
        super(ProxyServer, self).__init__()
        self.host = config["host"]
        self.port = config["port"]
        if proxy_server_handler is None:
            proxy_server_handler = ProxyServerHandler(config)
        self.proxy_server_handler = proxy_server_handler

    @gen.coroutine
    def handle_stream(self, stream, port):
        try:
            host, port = yield self.proxy_server_handler.read_and_return_addr(stream)
            dest_stream = yield self.proxy_server_handler.create_dest_stream(host, port)
            yield self.proxy_server_handler.run_next_layer(stream, dest_stream, host, port)
        except gen.TimeoutError:
            stream.close()
        except Exception as e:
            # not handle exception, log it and close the stream
            logger.exception(e)
            stream.close()

    def start_listener(self):
        self.listen(self.port, self.host)
        logger.info("proxy server is listening at {0}:{1}".format(self.host, self.port))


class ProxyServerHandler(object):
    def __init__(self, config, interceptor=None):
        super(ProxyServerHandler, self).__init__()
        self.mode = config["mode"]
        try:
            self.http_ports = config["http_port"]
        except KeyError:
            self.http_ports = []
        try:
            self.https_ports = config["https_port"]
        except KeyError:
            self.http_ports = []
        self.cert_file = config["certfile"]
        self.key_file = config["keyfile"]

        if interceptor is None:
            interceptor = self.create_interceptor(config)
        self.interceptor = interceptor
        self.proxy_handler = self.get_proxy_handler()

    def get_proxy_handler(self):
        if self.mode == "socks":
            return SocksProxyHandler()
        elif self.mode == "transparent":
            return TransparentProxyHandler()
        else:
            # fixme: due to fail fast, need raise exception here
            logger.warning("Unsupport proxy mode : {0}".format(self.mode))

    def create_interceptor(self, config):
        return Interceptor(config=config)

    def read_and_return_addr(self, stream):
        return self.proxy_handler.read_and_return_addr(stream)

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

    @gen.coroutine
    def run_next_layer(self, src_stream, dest_stream, host, port):
        if (port == 443 or port in self.https_ports):
            try:
                src_ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
                src_ssl_context.load_cert_chain(certfile=self.cert_file,
                                                keyfile=self.key_file)
                src_stream = yield src_stream.start_tls(server_side=True, ssl_options=src_ssl_context)

                # Will not verify the server side
                dest_ssl_context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
                dest_ssl_context.check_hostname = False
                dest_ssl_context.verify_mode = ssl.CERT_NONE

                dest_stream = yield dest_stream.start_tls(server_side=False, ssl_options=dest_ssl_context)
            except Exception as e:
                logger.exception(e)

        context = Context(src_stream=src_stream,
                          dest_stream=dest_stream,
                          interceptor=self.interceptor,
                          host=host,
                          port=port)
        self.get_layer(context).process()

    def get_layer(self, context):
        http_ports = [80, 443]
        http_ports.extend(self.http_ports)
        http_ports.extend(self.https_ports)
        if context.port in http_ports:
            return Http1Layer(context)
        else:
            return ForwardLayer(context)


def start_proxy_server(config):
    server = ProxyServer(config)
    server.start_listener()

    try:
        curr_loop().start()
    except KeyboardInterrupt:
        # fixme: gracefully stop everything
        logger.info("bye")
