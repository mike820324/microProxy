from copy import copy
from tornado import iostream
from tornado import gen
from tornado import httputil
from tornado import http1connection
from tornado import concurrent
from blinker import signal

from microproxy.utils import get_logger
from microproxy.exception import SrcStreamClosedError, DestStreamClosedError
from microproxy.context import HttpRequest, HttpResponse
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
        http_server_connection = http1connection.HTTP1ServerConnection(
            self.context.src_stream)
        http_server_connection.start_serving(self)
        return self._future

    def start_request(self, server_conn, request_conn):
        dest_conn = http1connection.HTTP1Connection(
            self.context.dest_stream, True)
        self.http_forwarder = HttpForwarder(
            self.context, request_conn, dest_conn, self)
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
        log_debug_with_http_info(
            self.context, "source request headers recieved")
        headers_dict = {k: v for k, v in headers.get_all()}
        self.req = HttpRequest(version=start_line.version,
                               method=start_line.method,
                               path=start_line.path,
                               headers=headers_dict)

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

        plugin_response = signal_request.send(
            self, layer_context=self.context, request=sender.req)
        self.req = plugin_response[0][1].request if len(plugin_response) else sender.req

        status_line = httputil.RequestStartLine(self.req.method,
                                                self.req.path,
                                                self.req.version)
        try:
            yield self.dest_conn.write_headers(
                status_line,
                httputil.HTTPHeaders(self.req.headers.get_dict()))
            yield self.dest_conn.write(self.req.body)
            yield self.dest_conn.read_response(self.create_resp_reader())
            log_debug_with_http_info(self.context, "destination request done")
        except iostream.StreamClosedError as e:
            log_debug_with_http_info(
                self.context, "destination closed while writing/reading")
            signal("http1layer_error").send(self.http1_layer,
                                            exe_info=DestStreamClosedError(e))
        except Exception as e:
            signal("http1layer_error").send(self.http1_layer, exe_info=e)

    @gen.coroutine
    def resp_done(self, sender):
        log_debug_with_http_info(self.context, "destination response done")

        plugin_response = signal_response.send(
            self, layer_context=self.context, request=self.req, response=sender.resp)

        self.resp = plugin_response[0][1].response if len(plugin_response) else sender.resp

        signal_publish.send(
            self, layer_context=self.context,
            request=self.req, response=self.resp)

        headers = self.resp.headers.get_dict()
        # NOTE: restriction on using tornado http connection.
        # If Transfer-Encoding is in header,
        # the source cannot receive chunks response properly.
        if "Transfer-Encoding" in headers:
            del headers["Transfer-Encoding"]

        status_line = httputil.ResponseStartLine(
            self.resp.version,
            self.resp.code,
            self.resp.reason)
        try:
            yield self.src_conn.write_headers(
                status_line,
                httputil.HTTPHeaders(headers))
            yield self.src_conn.write(self.resp.body)
            self.src_conn.finish()
            log_debug_with_http_info(self.context, "source response done")
        except iostream.StreamClosedError as e:
            log_debug_with_http_info(
                self.context, "source stream closed while writing")
            signal("http1layer_error").send(self.http1_layer,
                                            exe_info=SrcStreamClosedError(e))
        except Exception as e:
            signal("http1layer_error").send(self.http1_layer, exe_info=e)


class HttpRespReader(httputil.HTTPMessageDelegate):
    def __init__(self, context):
        super(HttpRespReader, self).__init__()
        self.context = context

    def headers_received(self, start_line, headers):
        log_debug_with_http_info(
            self.context, "destination response headers recieved")
        headers_dict = {k: v for k, v in headers.get_all()}
        self.resp = HttpResponse(code=start_line.code,
                                 reason=start_line.reason,
                                 version=start_line.version,
                                 headers=headers_dict)

    def data_received(self, chunk):
        log_debug_with_http_info(
            self.context, "destination response data recieved")
        self.resp.body += bytes(chunk)

    def finish(self):
        signal("response_done").send(self)

    def on_connection_close(self):
        log_debug_with_http_info(
            self.context, "destination connection closed")
