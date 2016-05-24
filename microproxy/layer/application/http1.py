from tornado import iostream
from tornado import gen
from tornado import httputil
from tornado import http1connection
from tornado import concurrent
from blinker import signal

from microproxy.utils import get_logger
from microproxy.exception import SrcStreamClosedError, DestStreamClosedError
from microproxy import http

logger = get_logger(__name__)


class Http1Layer(httputil.HTTPServerConnectionDelegate):
    def __init__(self, context):
        super(Http1Layer, self).__init__()
        self.context = context
        self.http_forwarder = None
        self._future = concurrent.Future()
        signal("http1layer_error").connect(self.on_error, sender=self)

    @gen.coroutine
    def process(self):
        http_server_connection = http1connection.HTTP1ServerConnection(self.context.src_stream)
        http_server_connection.start_serving(self)
        yield self._future

    def start_request(self, server_conn, request_conn):
        dest_conn = http1connection.HTTP1Connection(self.context.dest_stream,
                                                    True)
        self.http_forwarder = HttpForwarder(self.context,
                                            request_conn,
                                            dest_conn,
                                            self)
        return self.http_forwarder.create_req_reader()

    def on_close(self, server_conn):
        logger.debug("http layer done")
        if self._future.running():
            self._future.set_result(None)

    def on_error(self, sender, exe_info=None):
        logger.debug("http layer error")
        self._future.set_exception(exe_info)


class HttpReqReader(httputil.HTTPMessageDelegate):
    def __init__(self, context):
        super(HttpReqReader, self).__init__()
        self.context = context

    def headers_received(self, start_line, headers):
        logger.debug("source request headers recieved")
        self.req = http.HttpRequest(version=start_line.version,
                                    method=start_line.method,
                                    path=start_line.path,
                                    headers=headers)

    def data_received(self, chunk):
        logger.debug("source request recieved")
        self.req.body += bytes(chunk)

    def finish(self):
        signal("request_done").send(self)

    def on_connection_close(self):
        logger.debug("source connection close")


class HttpForwarder(object):
    def __init__(self, context, src_conn, dest_conn, http1_layer):
        super(HttpForwarder, self).__init__()
        self.context = context
        self.src_conn = src_conn
        self.dest_conn = dest_conn
        self.http1_layer = http1_layer
        self.req = None
        self.resp = None

    def create_req_reader(self):
        reader = HttpReqReader(self.context)

        signal("request_done").connect(self.req_done, sender=reader)
        return reader

    def create_resp_reader(self):
        reader = HttpRespReader(self.context)

        signal("response_done").connect(self.resp_done, sender=reader)
        return reader

    @gen.coroutine
    def req_done(self, sender):
        logger.debug("source request done")
        self.req = sender.req
        signal("interceptor_request").send(self, request=self.req)

        status_line = httputil.RequestStartLine(self.req.method,
                                                self.req.path,
                                                self.req.version)
        try:
            yield self.dest_conn.write_headers(status_line, self.req.headers)
            yield self.dest_conn.write(self.req.body)
            yield self.dest_conn.read_response(self.create_resp_reader())
            logger.debug("destination request done")
        except iostream.StreamClosedError as e:
            logger.debug("destination closed while writing/reading")
            signal("http1layer_error").send(self.http1_layer,
                                            exe_info=DestStreamClosedError(e))
        except Exception as e:
            signal("http1layer_error").send(self.http1_layer, exe_info=e)

    @gen.coroutine
    def resp_done(self, sender):
        logger.debug("destination response done")
        self.resp = sender.resp
        signal("interceptor_response").send(self, response=self.resp)
        signal("interceptor_record").send(self,
                                          request=self.req,
                                          response=self.resp)

        headers = self.resp.headers.copy()
        # restriction on using tornado http connection
        # pass Transfer-Encoding in header will let the source cannot receive chunks response correctly
        if headers.get("Transfer-Encoding"):
            del headers["Transfer-Encoding"]

        status_line = httputil.ResponseStartLine(self.resp.version,
                                                 self.resp.code,
                                                 self.resp.reason)
        try:
            yield self.src_conn.write_headers(status_line, headers)
            yield self.src_conn.write(self.resp.body)
            self.src_conn.finish()
            logger.debug("source response done")
        except iostream.StreamClosedError as e:
            logger.debug("source stream closed while writing")
            signal("http1layer_error").send(self.http1_layer,
                                            exe_info=SrcStreamClosedError(e))
        except Exception as e:
            signal("http1layer_error").send(self.http1_layer, exe_info=e)


class HttpRespReader(httputil.HTTPMessageDelegate):
    def __init__(self, context):
        super(HttpRespReader, self).__init__()
        self.context = context

    def headers_received(self, start_line, headers):
        logger.debug("destination response headers received")
        self.resp = http.HttpResponse(code=start_line.code,
                                      reason=start_line.reason,
                                      version=start_line.version,
                                      headers=headers)

    def data_received(self, chunk):
        logger.debug("destination response data received")
        self.resp.body += bytes(chunk)

    def finish(self):
        signal("response_done").send(self)

    def on_connection_close(self):
        logger.debug("destination connection closed")
