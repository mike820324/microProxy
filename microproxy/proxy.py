import struct
import socket

import tornado.tcpserver
import tornado.iostream
import tornado.netutil
import tornado.gen

import http
from http import HttpMessageBuilder
from utils import curr_loop
import msg_publisher

import logging
logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class AbstractServer(object):
    def __init__(self, target_src_stream, dest_stream):
        super(AbstractServer, self).__init__()
        self.target_src_stream = target_src_stream
        self.target_dest_stream = dest_stream

    def start_server(self):
        logger.info("{0} socket is ready for process the request".format(__name__))
        self.is_src_close = False
        self.target_src_stream.read_until_close(streaming_callback=self.on_request)
        self.target_src_stream.set_close_callback(self.on_src_close)

        self.is_dest_close = False
        self.target_dest_stream.read_until_close(streaming_callback=self.on_response)
        self.target_dest_stream.set_close_callback(self.on_dest_close)

    def on_src_close(self):
        raise NotImplementedError

    def on_dest_close(self):
        raise NotImplementedError

    def on_request(self, data):
        raise NotImplementedError

    def on_response(self, data):
        raise NotImplementedError


class HttpLayer(AbstractServer):
    CONNECT = 0
    REQUEST_IN = 1
    REQUEST_OUT = 2
    RESPONSE_IN = 3
    RESPONSE_OUT = 4

    '''
    HTTPServer: HTTPServer will handle http trafic.
    '''
    def __init__(self, target_src_stream, dest_stream, publisher):
        super(HttpLayer, self).__init__(target_src_stream, dest_stream)
        self.state = self.CONNECT
        self.request_builder = HttpMessageBuilder()
        self.response_builder = HttpMessageBuilder()
        self.current_result = {}
        self.publisher = publisher

    def on_src_close(self):
        # fixme: better handling
        if not self.target_dest_stream.closed():
            self.target_dest_stream.close()

    def on_dest_close(self):
        # fixme: better handling
        if not self.target_src_stream.closed():
            self.target_src_stream.close()

    def req_to_destination(self, request):
        logger.debug("request out")
        self.target_dest_stream.write(http.assemble_request(request))
        self.request_builder = HttpMessageBuilder()
        self.state = self.REQUEST_OUT

    def res_to_source(self, response):
        logger.debug("response out")
        for chunk in http.assemble_responses(response):
            try:
                self.target_src_stream.write(chunk)
            except tornado.iostream.StreamClosedError:
                self.on_src_close()
        self.response_builder = HttpMessageBuilder()
        self.state = self.RESPONSE_OUT

    def on_request(self, data):
        logger.debug("request in")
        self.state = self.REQUEST_IN
        self.request_builder.parse(data)
        if self.request_builder.is_done and not self.target_dest_stream.closed():
            logger.debug("request in complete")
            http_message = self.request_builder.build()
            self.current_result["request"] = http.serialize(http_message)
            self.req_to_destination(http_message)

    def on_response(self, data):
        logger.debug("response in")
        self.state = self.RESPONSE_IN
        self.response_builder.parse(data)
        if self.response_builder.is_done and not self.target_src_stream.closed():
            logger.debug("request out complete")
            http_message = self.response_builder.build()
            self.current_result["response"] = http.serialize(http_message)
            self.res_to_source(http_message)
            self.record()

    def record(self):
        self.publisher.publish(self.current_result)


class TLSLayer(AbstractServer):
    '''
    TLSLayer: passing all the src data to destination. Will not intercept anything
    '''
    def __init__(self, target_src_stream, dest_stream):
        super(TLSLayer, self).__init__(target_src_stream, dest_stream)
        self.is_tls = None

    def is_tls_protocol(self, data):
        return (
            data[0] == '\x16' and
            data[1] == '\x03' and
            data[2] in ('\x00', '\x01', '\x02', '\x03')
        )

    def on_src_close(self):
        self.is_src_close = True

    def on_dest_close(self):
        self.is_dest_close = True

    def on_request(self, data):
        if not self.is_dest_close:
            self.target_dest_stream.write(data)

    def on_response(self, data):
        if not self.is_src_close:
            self.target_src_stream.write(data)


class DirectServer(AbstractServer):
    '''
    DirectServer: passing all the src data to destination. Will not intercept anything
    '''
    def __init__(self, target_src_stream, dest_stream):
        super(DirectServer, self).__init__(target_src_stream, dest_stream)

    def on_src_close(self):
        self.is_src_close = True

    def on_dest_close(self):
        self.is_dest_close = True

    def on_request(self, data):
        if not self.is_dest_close:
            self.target_dest_stream.write(data)

    def on_response(self, data):
        if not self.is_src_close:
            self.target_src_stream.write(data)


class SocksLayer(object):
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

    def __init__(self, stream):
        super(SocksLayer, self).__init__()
        self.src_stream = stream

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
        self.dest_stream = tornado.iostream.IOStream(s)

    @tornado.gen.coroutine
    def read(self):
        data = yield self.src_stream.read_bytes(3)
        yield self.socks_greeting(data)

        data = yield self.src_stream.read_bytes(4)
        yield self.socks_request(data)

    @tornado.gen.coroutine
    def socks_greeting(self, data):
        logger.info("socks greeting to {0}".format(self.src_stream.socket.getpeername()[0]))
        socks_init_data = struct.unpack('BBB', data)
        socks_version = socks_init_data[0]
        socks_nmethod = socks_init_data[1]
        socks_methods = socks_init_data[2]

        if socks_version != self.SOCKS_VERSION:
            logger.warning("Socks Version incorrent : {}".format(socks_version))
            # fixme: response with error
            self.src_stream.close()

        if socks_nmethod != 1:
            logger.warning("SOCKS5 Auth not supported")
            # fixme: response with error
            self.src_stream.close()
        else:
            response = struct.pack('BB', self.SOCKS_VERSION, 0)
            yield self.src_stream.write(response)

    @tornado.gen.coroutine
    def socks_request(self, data):
        request_header_data = struct.unpack('!BBxB', data)
        socks_version = request_header_data[0]
        socks_cmd = request_header_data[1]
        socks_atyp = request_header_data[2]

        if socks_version != self.SOCKS_VERSION:
            logger.warning("Socks Version incorrent : {}".format(socks_version))
            # fixme: response with error
            self.src_stream.close()

        if socks_cmd != self.SOCKS_REQ_COMMAND["CONNECT"]:
            logger.warning("Socks Command Not Supported : {}".format(socks_cmd))
            # fixme: response with error
            self.src_stream.close()

        if socks_atyp == self.SOCKS_ADDR_TYPE["IPV6"]:
            logger.warning("Socks Address Type Not Supported : {}".format(socks_atyp))
            # fixme: response with error
            self.src_stream.close()

        elif socks_atyp == self.SOCKS_ADDR_TYPE["IPV4"]:
            data = yield self.src_stream.read_bytes(6)
            request_info = struct.unpack("!IH", data)
            dest_addr_info = (socket.inet_ntoa(struct.pack('!I', request_info[0])),
                              request_info[1])
            response = struct.pack('!BBxBIH',
                                   self.SOCKS_VERSION,
                                   self.SOCKS_RESP_STATUS["SUCCESS"],
                                   self.SOCKS_ADDR_TYPE["IPV4"],
                                   *request_info)

        elif socks_atyp == self.SOCKS_ADDR_TYPE["DOMAINNAME"]:
            data = yield self.src_stream.read_bytes(1)
            host_length = struct.unpack("!B", data)[0]

            data = yield self.src_stream.read_bytes(host_length + 2)
            dest_addr_info = struct.unpack("!{0}sH".format(host_length), data)
            response = struct.pack("!BBxBB{0}sH".format(host_length),
                                   self.SOCKS_VERSION,
                                   self.SOCKS_RESP_STATUS["SUCCESS"],
                                   self.SOCKS_ADDR_TYPE["DOMAINNAME"],
                                   host_length,
                                   *dest_addr_info)


        logger.info("socks request to {0}:{1}".format(*dest_addr_info))
        yield self.dest_stream.connect(dest_addr_info)
        yield self.src_stream.write(response)


class ProxyServer(tornado.tcpserver.TCPServer):
    def __init__(self, host, port):
        super(ProxyServer, self).__init__()
        self.host = host
        self.port = port
        self.publisher = msg_publisher.create()

    @tornado.gen.coroutine
    def handle_stream(self, stream, port):
        socks_layer = SocksLayer(stream)
        yield socks_layer.read()
        self.create_http_server(socks_layer.src_stream, socks_layer.dest_stream).start_server()

    def create_http_server(self, src_stream, dest_stream):
        dest_port = dest_stream.socket.getpeername()[1]
        if dest_port == 5000 or dest_port == 80:
            return HttpLayer(src_stream, dest_stream, self.publisher)
        elif dest_port == 5001 or dest_port == 443:
            return TLSLayer(src_stream, dest_stream)
        else:
            return DirectServer(src_stream, dest_stream)

    def start_listener(self):
        self.listen(self.port, self.host)
        logger.info("proxy server is listening at {0}:{1}".format(self.host, self.port))


def start_proxy_server(host, port):
    server = ProxyServer(host, port)
    server.start_listener()

    try:
        curr_loop().start()
    except KeyboardInterrupt:
        logger.info("bye")
