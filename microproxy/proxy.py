import socket
import datetime

from tornado import tcpserver
from tornado import iostream
from tornado import gen
from tornado import httputil
from tornado import http1connection

import http
import mode
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


class HttpLayer(httputil.HTTPServerConnectionDelegate):
    def __init__(self, context):
        super(HttpLayer, self).__init__()
        self.context = context

    def process(self):
        http_server_connection = http1connection.HTTP1ServerConnection(self.context.src_stream)
        http_server_connection.start_serving(self)

    def start_request(self, server_conn, request_conn):
        dest_conn = http1connection.HTTP1Connection(self.context.dest_stream,
                                                    True)
        http_forwarder = HttpForwarder(self.context,
                                       request_conn,
                                       dest_conn)
        return http_forwarder.create_req_reader()

    def on_close(self, server_conn):
        self.context.dest_stream.close()
        logger.debug("http layer done")


class HttpReqReader(httputil.HTTPMessageDelegate):
    def __init__(self, context, http_forwarder):
        super(HttpReqReader, self).__init__()
        self.context = context
        self.http_forwarder = http_forwarder
        self._chunks = []

    def headers_received(self, start_line, headers):
        logger.debug("source request headers recieved")
        self.req = http.HttpRequest(version=start_line.version,
                                    method=start_line.method,
                                    path=start_line.path,
                                    headers=headers)

    def data_received(self, chunk):
        logger.debug("source request recieved")
        self._chunks.append(chunk)

    def finish(self):
        self.req.body = b"".join(self._chunks)
        self.http_forwarder.req_done(self.req)

    def on_connection_close(self):
        logger.debug("source connection close")
        self.http_forwarder.close_dest_conn()


class HttpForwarder(object):
    def __init__(self, context, src_conn, dest_conn):
        super(HttpForwarder, self).__init__()
        self.context = context
        self.src_conn = src_conn
        self.dest_conn = dest_conn
        self.req = None
        self.resp = None

    def create_req_reader(self):
        return HttpReqReader(self.context,
                             self)

    def create_resp_reader(self):
        return HttpRespReader(self.context,
                              self)

    @gen.coroutine
    def req_done(self, req):
        logger.debug("source request done")
        self.req = req
        if self.context.interceptor:
            self.context.interceptor.request(req)

        status_line = httputil.RequestStartLine(req.method,
                                                req.path,
                                                req.version)
        try:
            yield self.dest_conn.write_headers(status_line, req.headers)
            yield self.dest_conn.write(req.body)
            yield self.dest_conn.read_response(self.create_resp_reader())
            logger.debug("destination request done")
        except iostream.StreamClosedError:
            logger.debug("destination closed while writing/reading")
            self.close_src_conn()
        except Exception as e:
            logger.exception(e)

    @gen.coroutine
    def resp_done(self, resp):
        logger.debug("destination response done")
        self.resp = resp
        if self.context.interceptor:
            self.context.interceptor.response(resp)
            self.context.interceptor.record(self.req, self.resp)

        headers = resp.headers.copy()
        # restriction on using tornado http connection
        # pass Transfer-Encoding in header will let the source cannot receive chunks response correctly
        if headers.get("Transfer-Encoding"):
            del headers["Transfer-Encoding"]

        status_line = httputil.ResponseStartLine(resp.version,
                                                 resp.code,
                                                 resp.reason)
        try:
            yield self.src_conn.write_headers(status_line, headers)
            yield self.src_conn.write(resp.body)
            self.src_conn.finish()
            logger.debug("source response done")
        except iostream.StreamClosedError:
            logger.debug("source stream closed while writing")
            self.close_dest_conn()
        except Exception as e:
            logger.exception(e)

    def close_src_conn(self):
        self.src_conn.close()

    def close_dest_conn(self):
        self.dest_conn.close()


class HttpRespReader(httputil.HTTPMessageDelegate):
    def __init__(self, context, http_forwarder):
        super(HttpRespReader, self).__init__()
        self.context = context
        self.http_forwarder = http_forwarder
        self._chunks = []

    def headers_received(self, start_line, headers):
        logger.debug("destination response headers received")
        self.resp = http.HttpResponse(code=start_line.code,
                                      reason=start_line.reason,
                                      version=start_line.version,
                                      headers=headers)

    def data_received(self, chunk):
        logger.debug("destination response data received")
        self._chunks.append(chunk)

    def finish(self):
        self.resp.body = b"".join(self._chunks)
        self.http_forwarder.resp_done(self.resp)

    def on_connection_close(self):
        logger.debug("destination connection closed")
        self.http_forwarder.close_src_conn()


class TLSHandler(AbstractHandler):
    '''
    TLSHandler: handle tls connection
    '''
    def process(self, context):
        ForwardLayer(context).process()


class DirectHandler(AbstractHandler):
    def process(self, context):
        ForwardLayer(context).process()


class ForwardLayer(object):
    '''
    ForwardLayer: passing all the src data to destination. Will not intercept anything
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


class ProxyServer(tcpserver.TCPServer):
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

    @gen.coroutine
    def handle_stream(self, stream, port):
        proxy_handler = self.get_proxy_handler()
        try:
            dest_addr_info = yield proxy_handler.read_and_return_addr(stream)
            dest_stream = yield self.create_dest_stream(dest_addr_info)
            stream_handler = self._get_stream_handler(dest_addr_info[1])
            context = Context(stream,
                              dest_stream,
                              self.interceptor)
            stream_handler.process(context)
        except gen.TimeoutError:
            stream.close()

    def get_proxy_handler(self):
        if self.mode == "socks":
            return mode.SocksProxyHandler()
        elif self.mode == "transparent":
            return mode.TranparentProxyHandler()
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

    @gen.coroutine
    def create_dest_stream(self, dest_addr_info):
        dest_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
        dest_stream = iostream.IOStream(dest_socket)
        try:
            yield gen.with_timeout(datetime.timedelta(5), dest_stream.connect(dest_addr_info))
            raise gen.Return(dest_stream)
        except gen.TimeoutError:
            logger.warning("Connect to Destination Timeout")
            raise


def start_proxy_server(config):
    server = ProxyServer(config)
    server.start_listener()

    try:
        curr_loop().start()
    except KeyboardInterrupt:
        # fixme: gracefully stop everything
        logger.info("bye")
