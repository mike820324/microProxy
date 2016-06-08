from copy import copy
from tornado import iostream
from tornado import gen
from tornado import httputil
from tornado import http1connection
from tornado import concurrent
from blinker import signal

from microproxy.utils import get_logger
from microproxy.exception import SrcStreamClosedError, DestStreamClosedError
from microproxy import http
from microproxy.interceptor import signal_request, signal_response, signal_publish

logger = get_logger(__name__)


def log_debug_with_http_info(context, msg):
    logger.debug("{0}://{1}:{2} -> {3}".format(context.scheme,
                                               context.host,
                                               context.port,
                                               msg))


class Http1Layer(httputil.HTTPServerConnectionDelegate):
    def __init__(self, context):
        super(Http1Layer, self).__init__()
        self.context = copy(context)
        self.http_forwarder = None
        self._future = concurrent.Future()
        signal("http1layer_error").connect(self.on_error, sender=self)

    def process_and_return_context(self):
        http_server_connection = http1connection.HTTP1ServerConnection(self.context.src_stream)
        http_server_connection.start_serving(self)
        return self._future

    def start_request(self, server_conn, request_conn):
        dest_conn = http1connection.HTTP1Connection(self.context.dest_stream,
                                                    True)
        self.http_forwarder = HttpForwarder(self.context,
                                            request_conn,
                                            dest_conn,
                                            self)
        return self.http_forwarder.create_req_reader()

    def on_close(self, server_conn):
        log_debug_with_http_info(self.context, "http layer done")
        if self._future.running():
            self._future.set_result(self.context)

    def on_error(self, sender, exe_info=None):
        log_debug_with_http_info(self.context, "http layer error")
        self._future.set_exception(exe_info)


class HttpReqReader(httputil.HTTPMessageDelegate):
    def __init__(self, context):
        super(HttpReqReader, self).__init__()
        self.context = context

    def headers_received(self, start_line, headers):
        log_debug_with_http_info(self.context,
                                 "source request headers recieved")
        self.req = http.HttpRequest(version=start_line.version,
                                    method=start_line.method,
                                    path=start_line.path,
                                    headers=headers)

    def data_received(self, chunk):
        log_debug_with_http_info(self.context, "source request body recieved")
        self.req.body += bytes(chunk)

    def finish(self):
        signal("request_done").send(self)

    def on_connection_close(self):
        log_debug_with_http_info(self.context, "source connection closed")


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
        log_debug_with_http_info(self.context, "source request done")
        requests = signal_request.send(self, request=sender.req)
        if len(requests) > 1:
            logger.error("More than one interceptor")

        try:
            _, new_request = requests[0]
        except IndexError:
            new_request = sender.req
            logger.debug("No interceptor is listening")

        self.req = new_request
        status_line = httputil.RequestStartLine(self.req.method,
                                                self.req.path,
                                                self.req.version)
        try:
            yield self.dest_conn.write_headers(status_line, self.req.headers)
            yield self.dest_conn.write(self.req.body)
            yield self.dest_conn.read_response(self.create_resp_reader())
            log_debug_with_http_info(self.context, "destination request done")
        except iostream.StreamClosedError as e:
            log_debug_with_http_info(self.context, "destination closed while writing/reading")
            signal("http1layer_error").send(self.http1_layer,
                                            exe_info=DestStreamClosedError(e))
        except Exception as e:
            signal("http1layer_error").send(self.http1_layer, exe_info=e)

    @gen.coroutine
    def resp_done(self, sender):
        log_debug_with_http_info(self.context, "destination response done")
        responses = signal_response.send(self, response=sender.resp)

        if len(responses) > 1:
            logger.error("More than one interceptor")
        try:
            _, new_response = responses[0]
        except IndexError:
            new_response = sender.resp
            logger.debug("No Interceptor is listening")

        self.resp = new_response
        signal_publish.send(self,
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
            log_debug_with_http_info(self.context, "source response done")
        except iostream.StreamClosedError as e:
            log_debug_with_http_info(self.context, "source stream closed while writing")
            signal("http1layer_error").send(self.http1_layer,
                                            exe_info=SrcStreamClosedError(e))
        except Exception as e:
            signal("http1layer_error").send(self.http1_layer, exe_info=e)


class HttpRespReader(httputil.HTTPMessageDelegate):
    def __init__(self, context):
        super(HttpRespReader, self).__init__()
        self.context = context

    def headers_received(self, start_line, headers):
        log_debug_with_http_info(self.context,
                                 "destination response headers recieved")
        self.resp = http.HttpResponse(code=start_line.code,
                                      reason=start_line.reason,
                                      version=start_line.version,
                                      headers=headers)

    def data_received(self, chunk):
        log_debug_with_http_info(self.context, "destination response data recieved")
        self.resp.body += bytes(chunk)

    def finish(self):
        signal("response_done").send(self)

    def on_connection_close(self):
        log_debug_with_http_info(self.context, "destination connection closed")
