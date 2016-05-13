import struct
import socket
import platform
import datetime

import tornado.tcpserver
import tornado.iostream
import tornado.netutil
import tornado.gen
import tornado.httputil
import tornado.http1connection

import http
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
    def process(self, context):
        http_layer = HttpLayer(context)
        http_layer.process()


def _close_all_stream(context):
    logger.debug("stream close")
    if not context.src_stream.closed():
        context.src_stream.close()
    if not context.dest_stream.closed():
        context.dest_stream.close()


class HttpLayer(tornado.httputil.HTTPServerConnectionDelegate):
    def __init__(self, context):
        super(HttpLayer, self).__init__()
        self.context = context

    def process(self):
        http_server_connection = tornado.http1connection.HTTP1ServerConnection(self.context.src_stream)
        http_server_connection.start_serving(self)

    def start_request(self, server_conn, request_conn):
        return _HttpReqToDest(self.context, request_conn)

    def on_close(self, server_conn):
        logger.debug("http layer done")
        _close_all_stream(self.context)


class _HttpReqToDest(tornado.httputil.HTTPMessageDelegate):
    def __init__(self, context, src_conn):
        super(_HttpReqToDest, self).__init__()
        self.context = context
        self.src_conn = src_conn
        self._chunks = []
        self.interceptor = _HttpInterceptor(context, src_conn)

    def headers_received(self, start_line, headers):
        logger.debug("source request headers recieved")
        self.req = http.HttpRequest(
            version=start_line.version,
            method=start_line.method,
            path=start_line.path,
            headers=headers)

    def data_received(self, chunk):
        logger.debug("source request recieved")
        self._chunks.append(chunk)

    def finish(self):
        self.req.body = b"".join(self._chunks)
        try:
            self.interceptor.req_done(self.req)
        except Exception as e:
            logger.exception(e)

    def on_connection_close(self):
        logger.debug("source connection close")
        _close_all_stream(self.context)


class _HttpInterceptor(object):
    def __init__(self, context, src_conn):
        super(_HttpInterceptor, self).__init__()
        self.context = context
        self.src_conn = src_conn
        self.dest_conn = tornado.http1connection.HTTP1Connection(
            context.dest_stream, True)
        self.req = None
        self.resp = None

    def req_done(self, req):
        logger.debug("source request done")
        self.req = req
        self.context.interceptor.request(req)

        self.dest_conn.write_headers(
            tornado.httputil.RequestStartLine(req.method, req.path, req.version),
            req.headers)
        self.dest_conn.write(req.body)
        self.dest_conn.read_response(_HttpRespToSrc(self.context, self))
        logger.debug("destination request done")

    def resp_done(self, resp):
        try:
            logger.debug("destination response done")
            self.resp = resp
            self.context.interceptor.response(resp)
            self.context.interceptor.record(self.req, self.resp)
         
            headers = resp.headers.copy()
            if headers.get("Transfer-Encoding"):
                del headers["Transfer-Encoding"]
            self.src_conn.write_headers(
                tornado.httputil.ResponseStartLine(resp.version, resp.code, resp.reason),
                headers)
            for chunk in resp.chunks:
                logger.debug("write chunk with length {0}".format(len(chunk)))
                self.src_conn.write(chunk)
            self.src_conn.finish()
            logger.debug("source response done")
        except Exception as e:
            logger.exception(e)


class _HttpRespToSrc(tornado.httputil.HTTPMessageDelegate):
    def __init__(self, context, interceptor):
        super(_HttpRespToSrc, self).__init__()
        self.context = context
        self.interceptor = interceptor
        self._chunks = []

    def headers_received(self, start_line, headers):
        logger.debug("destination response headers received")
        self.resp = http.HttpResponse(
            code=start_line.code,
            reason=start_line.reason,
            version=start_line.version,
            headers=headers)

    def data_received(self, chunk):
        logger.debug("destination response data received")
        self._chunks.append(chunk)

    def finish(self):
        try:
            self.resp.parse_body(self._chunks)
            self.interceptor.resp_done(self.resp)
        except Exception as e:
            logger.exception(e)

    def on_connection_close(self):
        logger.debug("destination connection closed")
        _close_all_stream(self.context)


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
        try:
            data = yield src_stream.read_bytes(3)
            yield self.socks_greeting(src_stream, data)
            data = yield src_stream.read_bytes(4)
            dest_addr_info = yield self.socks_request(src_stream, data)
            raise tornado.gen.Return(dest_addr_info)
        except tornado.iostream.StreamClosedError:
            logger.warning("Source Stream Closed")

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

    def _get_dest_addr(self, src_stream):
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
        raise tornado.gen.Return(self._get_dest_addr(src_stream))


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
        try:
            dest_addr_info = yield proxy_handler.read_and_return_addr(stream)
            dest_stream = yield self.create_dest_stream(dest_addr_info)
            stream_handler = self._get_stream_handler(dest_addr_info[1])
            context = Context(stream,
                              dest_stream,
                              self.interceptor)
            stream_handler.process(context)
        except tornado.gen.TimeoutError:
            stream.close()

    def get_proxy_handler(self):
        if self.mode == "socks":
            return SocksProxyHandler()
        elif self.mode == "transparent":
            return TranparentProxyHandler()
        else:
            # fixme: due to fail fast, need raise exception here
            logger.warning("Unsupport proxy mode : {0}".format(self.mode))

    def _get_stream_handler(self, port):
        if (port == 80 or port in self.additional_port["http"]):
            return HttpHandler()
        elif (port == 443 or port in self.additional_port["https"]):
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
        try:
            yield tornado.gen.with_timeout(datetime.timedelta(5), dest_stream.connect(dest_addr_info))
            raise tornado.gen.Return(dest_stream)
        except tornado.gen.TimeoutError:
            logger.warning("Connect to Destination Timeout")
            raise


def start_proxy_server(config):
    server = ProxyServer(config)
    server.start_listener()

    try:
        curr_loop().start()
    except KeyboardInterrupt:
        logger.info("bye")
