import struct
import socket
import platform
import sys

import tornado.tcpserver
import tornado.iostream
import tornado.netutil
import tornado.gen

import http
from http import HttpMessageBuilder
from utils import curr_loop, get_logger
from interceptor import MsgPublisherInterceptor as Interceptor

logger = get_logger(__name__)


class Context(object):
    def __init__(self, src_stream, dest_stream, interceptor):
        self.src_stream = src_stream
        self.dest_stream = dest_stream
        self.interceptor = interceptor


class AbstractHandler(object):
    def process(self, context):
        raise NotImplementedError


class HttpHandler(AbstractHandler):
    @tornado.gen.coroutine
    def process(self, context):
        logger.debug("start HttpHandler process")
        http_layer = HttpLayer(context)
        try:
            while not http_layer.closed():
                yield http_layer.process()
        except tornado.iostream.StreamClosedError:
            logger.warning("stream closed")
        except:
            logger.exception("http handle failed")
        http_layer.close()
        logger.debug("end HttpHandler process")


class HttpLayer(object):
    '''
    HTTPServer: HTTPServer will handle http trafic.
    '''
    def __init__(self, context):
        self.context = context

    @tornado.gen.coroutine
    def process(self):
        logger.debug("start HttpLayer process")
        request = yield self.read(self.context.src_stream)
        self.context.interceptor.request(request)
        yield self.context.dest_stream.write(http.assemble_request(request))
        response = yield self.read(self.context.dest_stream)
        self.context.interceptor.response(response)
        self.resp_to_src(response)
        self.context.interceptor.record(request, response)
        logger.debug("end HttpLayer process")

    @tornado.gen.coroutine
    def read(self, stream):
        logger.debug("start read")
        http_message_builder = HttpMessageBuilder()
        while not http_message_builder.is_done:
            data = yield stream.read_bytes(sys.maxsize, partial=True)
            http_message_builder.parse(data)
        logger.debug("end read")
        raise tornado.gen.Return(http_message_builder.build())

    @tornado.gen.coroutine
    def resp_to_src(self, response):
        logger.debug("start resp_to_src")
        for chunk in http.assemble_responses(response):
            yield self.context.src_stream.write(chunk)
        logger.debug("end resp_to_src")

    def closed(self):
        return (
            self.context.src_stream.closed() or
            self.context.dest_stream.closed())

    def close(self):
        if not self.context.src_stream.closed():
            self.context.src_stream.close()
        if not self.context.dest_stream.closed():
            self.context.dest_stream.close()


class TLSHandler(AbstractHandler):
    def process(self, context):
        ForwardLayer(context).process()


class DirectHandler(AbstractHandler):
    def process(self, context):
        ForwardLayer(context).process()


class ForwardLayer(object):
    '''
    TLSLayer: passing all the src data to destination. Will not intercept anything
    '''
    def __init__(self, context):
        super(ForwardLayer, self).__init__()
        self.context = context

    def process(self):
        self.context.src_stream.read_until_close(streaming_callback=self.on_request)
        self.context.src_stream.set_close_callback(self.on_src_close)
        self.context.dest_stream.read_until_close(streaming_callback=self.on_response)
        self.context.dest_stream.set_close_callback(self.on_dest_close)

    def is_tls_protocol(self, data):
        return (
            data[0] == '\x16' and
            data[1] == '\x03' and
            data[2] in ('\x00', '\x01', '\x02', '\x03')
        )

    def on_src_close(self):
        if not self.context.dest_stream.closed():
            self.context.dest_stream.close()

    def on_dest_close(self):
        if not self.context.src_stream.closed():
            self.context.src_stream.close()

    def on_request(self, data):
        if not self.context.dest_stream.closed():
            self.context.dest_stream.write(data)

    def on_response(self, data):
        if not self.context.src_stream.closed():
            self.context.src_stream.write(data)


class ProxyHandler(object):
    def __init__(self):
        super(ProxyHandler, self).__init__()

    def read_and_return_addr(self, src_stream):
        raise NotImplementedError()


class SocksProxyHandler(ProxyHandler):
    SOCKS_VERSION = 0x05

    SOCKS_REQ_COMMAND = {
        "CONNECT": 0x1,
        "BIND": 0x02,
        "UDP_ASSOCIATE": 0x03
    }

    SOCKS_RESP_STATUS = {
        "SUCCESS": 0x0,
        "GENRAL_FAILURE": 0x01,
        "CONNECTION_NOT_ALLOWED": 0x02,
        "NETWORK_UNREACHABLE": 0x03,
        "HOST_UNREACHABLE": 0x04,
        "CONNECTION_REFUSED": 0x05,
        "TTL_EXPIRED": 0x06,
        "COMMAND_NOT_SUPPORTED": 0x07,
        "ADDRESS_TYPE_NOT_SUPPORTED": 0x08,
    }

    SOCKS_ADDR_TYPE = {
        "IPV4": 0x01,
        "DOMAINNAME": 0x03,
        "IPV6": 0x04
    }

    def __init__(self):
        super(SocksProxyHandler, self).__init__()

    @tornado.gen.coroutine
    def read_and_return_addr(self, src_stream):
        data = yield src_stream.read_bytes(3)
        yield self.socks_greeting(src_stream, data)

        data = yield src_stream.read_bytes(4)
        dest_addr_info = yield self.socks_request(src_stream, data)
        raise tornado.gen.Return(dest_addr_info)

    @tornado.gen.coroutine
    def socks_greeting(self, src_stream, data):
        logger.info("socks greeting to {0}".format(src_stream.socket.getpeername()[0]))
        socks_init_data = struct.unpack('BBB', data)
        socks_version = socks_init_data[0]
        socks_nmethod = socks_init_data[1]

        if socks_version != self.SOCKS_VERSION:
            logger.warning("Socks Version incorrent : {}".format(socks_version))
            # fixme: response with error
            src_stream.close()

        if socks_nmethod != 1:
            logger.warning("SOCKS5 Auth not supported")
            # fixme: response with error
            src_stream.close()
        else:
            response = struct.pack('BB', self.SOCKS_VERSION, 0)
            yield src_stream.write(response)

    @tornado.gen.coroutine
    def socks_request(self, src_stream, data):
        request_header_data = struct.unpack('!BBxB', data)
        socks_version = request_header_data[0]
        socks_cmd = request_header_data[1]
        socks_atyp = request_header_data[2]

        if socks_version != self.SOCKS_VERSION:
            logger.warning("Socks Version incorrent : {}".format(socks_version))
            # fixme: response with error
            src_stream.close()

        if socks_cmd != self.SOCKS_REQ_COMMAND["CONNECT"]:
            logger.warning("Socks Command Not Supported : {}".format(socks_cmd))
            # fixme: response with error
            src_stream.close()

        if socks_atyp == self.SOCKS_ADDR_TYPE["IPV6"]:
            logger.warning("Socks Address Type Not Supported : {}".format(socks_atyp))
            # fixme: response with error
            src_stream.close()

        elif socks_atyp == self.SOCKS_ADDR_TYPE["IPV4"]:
            data = yield src_stream.read_bytes(6)
            request_info = struct.unpack("!IH", data)
            dest_addr_info = (socket.inet_ntoa(struct.pack('!I', request_info[0])),
                              request_info[1])
            response = struct.pack('!BBxBIH',
                                   self.SOCKS_VERSION,
                                   self.SOCKS_RESP_STATUS["SUCCESS"],
                                   self.SOCKS_ADDR_TYPE["IPV4"],
                                   *request_info)

        elif socks_atyp == self.SOCKS_ADDR_TYPE["DOMAINNAME"]:
            data = yield src_stream.read_bytes(1)
            host_length = struct.unpack("!B", data)[0]

            data = yield src_stream.read_bytes(host_length + 2)
            dest_addr_info = struct.unpack("!{0}sH".format(host_length), data)
            response = struct.pack("!BBxBB{0}sH".format(host_length),
                                   self.SOCKS_VERSION,
                                   self.SOCKS_RESP_STATUS["SUCCESS"],
                                   self.SOCKS_ADDR_TYPE["DOMAINNAME"],
                                   host_length,
                                   *dest_addr_info)

        logger.info("socks request to {0}:{1}".format(*dest_addr_info))
        yield src_stream.write(response)
        raise tornado.gen.Return(dest_addr_info)


class TranparentProxyHandler(ProxyHandler):
    SO_ORIGINAL_DST = 80

    def __init__(self):
        super(TranparentProxyHandler, self).__init__()

    def _get_dst_addr(self, src_stream):
        # Currently, we only support Linux
        if platform.system() != "Linux":
            raise NotImplementedError

        sock_opt = src_stream.socket.getsockopt(socket.SOL_IP,
                                                self.SO_ORIGINAL_DST,
                                                16)

        _, port, a1, a2, a3, a4 = struct.unpack("!HHBBBBxxxxxxxx", sock_opt)
        address = "%d.%d.%d.%d" % (a1, a2, a3, a4)
        return address, port

    @tornado.gen.coroutine
    def read_and_return_addr(self, src_stream):
        raise tornado.gen.Return(self._get_dst_addr(src_stream))


class ProxyServer(tornado.tcpserver.TCPServer):
    def __init__(self, config):

        super(ProxyServer, self).__init__()
        self.host = config["host"]
        self.port = config["port"]
        self.mode = config["mode"]
        self.additional_port = {
            "http": config["http_port"],
            "https": config["https_port"]
        }
        self.interceptor = Interceptor(config=config)

    @tornado.gen.coroutine
    def handle_stream(self, stream, port):
        # fixme: expired time and timeout handler
        proxy_handler = self.get_proxy_handler()
        dest_addr_info = yield proxy_handler.read_and_return_addr(stream)
        dest_stream = yield self.create_dest_stream(dest_addr_info)
        stream_handler = self.get_stream_handler(stream, dest_stream)
        context = Context(
            stream,
            dest_stream,
            self.interceptor)
        stream_handler.process(context)

    def get_proxy_handler(self):
        if self.mode == "socks":
            return SocksProxyHandler()
        elif self.mode == "transparent":
            return TranparentProxyHandler()
        else:
            # fixme: due to fail fast, need raise exception here
            logger.warning("Unsupport proxy mode : {0}".format(self.mode))

    def get_stream_handler(self, src_stream, dest_stream):
        dest_port = dest_stream.socket.getpeername()[1]
        if (dest_port == 80 or dest_port in self.additional_port["http"]):
            return HttpHandler()
        elif (dest_port == 443 or dest_port in self.additional_port["https"]):
            return TLSHandler()
        else:
            return DirectHandler()

    def start_listener(self):
        self.listen(self.port, self.host)
        logger.info("proxy server is listening at {0}:{1}".format(self.host, self.port))

    @tornado.gen.coroutine
    def create_dest_stream(self, dest_addr_info):
        dest_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
        dest_stream = tornado.iostream.IOStream(dest_socket)
        yield dest_stream.connect(dest_addr_info)
        raise tornado.gen.Return(dest_stream)


def start_proxy_server(config):
    server = ProxyServer(config)
    server.start_listener()

    try:
        curr_loop().start()
    except KeyboardInterrupt:
        logger.info("bye")
