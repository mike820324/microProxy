from tornado import iostream
from tornado import gen
from tornado import httputil
from tornado import http1connection

from microproxy.utils import get_logger
from microproxy import http

logger = get_logger(__name__)


class Http1Layer(httputil.HTTPServerConnectionDelegate):
    def __init__(self, context):
        super(Http1Layer, self).__init__()
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
