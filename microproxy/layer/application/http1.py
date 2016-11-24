import h11
import re
from tornado import gen
from tornado.iostream import StreamClosedError

from microproxy.context import HttpResponse
from microproxy.exception import SrcStreamClosedError, DestStreamClosedError
from microproxy.layer.base import ApplicationLayer, DestStreamCreatorMixin
from microproxy.log import ProxyLogger
from microproxy.protocol.http1 import Connection

logger = ProxyLogger.get_logger(__name__)


def _wrap_req_path(context, req):
    return "http://{0}:{1}{2}".format(context.host, context.port, req.path)


def parse_proxy_path(path):
    default_ports = {
        "http": 80,
        "https": 443,
    }
    default_schemes = {
        80: "http",
        443: "https"
    }
    matcher = re.search(r"^((https?):\/\/)?([a-zA-Z0-9\.\-]+)(:(\d+))?(/.+)?", path)
    groups = matcher.groups() if matcher else []
    if not groups:
        raise ValueError("illegal proxy path {0}".format(path))
    else:
        scheme = groups[1] or ""
        host = groups[2]
        port = int(groups[4]) if groups[4] else 0

        if not scheme and not port:
            raise ValueError
        elif not scheme:
            scheme = default_schemes[port]
        elif not port:
            port = default_ports[scheme]

        return (scheme, host, port)


class Http1Layer(ApplicationLayer, DestStreamCreatorMixin):
    def __init__(self, server_state, context):
        super(Http1Layer, self).__init__(server_state, context)
        self.src_conn = Connection(
            h11.SERVER,
            self.src_stream,
            conn_type="src",
            readonly=(context.mode == "replay"),
            on_request=self.on_request)
        self.dest_conn = Connection(
            h11.CLIENT,
            self.dest_stream,
            conn_type="dest",
            on_response=self.on_response,
            on_info_response=self.on_info_response)
        self.req = None
        self.resp = None
        self.switch_protocol = False

    @gen.coroutine
    def process_and_return_context(self):
        while not self.finished():
            self.req = None
            self.resp = None
            try:
                yield self.read_request()
                yield self.handle_http_proxy()
                self.send_request()
                yield self.read_response()
                self.send_response()
            except SrcStreamClosedError:
                self.dest_stream.close()
                self.context.done = True
                if self.req:
                    raise
            except DestStreamClosedError:
                self.src_stream.close()
                raise
            except SwitchToTunnelHttpProxy:
                break

        if self.switch_protocol:
            self.context.scheme = self.req.headers["Upgrade"]
        raise gen.Return(self.context)

    @gen.coroutine
    def read_request(self):
        # NOTE: run first request to handle protocol change
        logger.debug("wait for request")
        while not self.req:
            try:
                data = yield self.src_stream.read_bytes(
                    self.src_stream.max_buffer_size, partial=True)
            except StreamClosedError:
                raise SrcStreamClosedError(self, detail="read request failed")
            else:
                self.src_conn.receive(data, raise_exception=True)
        logger.debug("received request: {0}".format(self.req))

    @gen.coroutine
    def read_response(self):
        logger.debug("wait for response")
        while not self.resp:
            try:
                data = yield self.dest_stream.read_bytes(
                    self.dest_stream.max_buffer_size, partial=True)
            except StreamClosedError:
                # NOTE: for HTTP protocol, there is some condition that response finish when they didn't send data
                # It may happen when there is no "Content-Length" or "Content-Encoding: chunked" defined in there header
                self.dest_conn.receive(b"", raise_exception=False)
                break
            else:
                self.dest_conn.receive(data, raise_exception=True)
        logger.debug("received response: {0}".format(self.resp))

    def on_request(self, request):
        plugin_result = self.interceptor.request(
            layer_context=self.context, request=request)

        self.req = plugin_result.request if plugin_result else request

    def send_request(self):
        try:
            self.dest_conn.send_request(self.req)
        except StreamClosedError:
            raise DestStreamClosedError(self, detail="send request failed with {0}".format(
                _wrap_req_path(self.context, self.req)))

    def on_response(self, response):
        plugin_result = self.interceptor.response(
            layer_context=self.context,
            request=self.req, response=response)

        self.resp = plugin_result.response if plugin_result else response

    def send_response(self):
        try:
            if int(self.resp.code) in range(200, 600):
                self.src_conn.send_response(self.resp)
                self.finish()
            else:
                self.src_conn.send_info_response(self.resp)
                self.finish(switch_protocol=True)
        except StreamClosedError:
            raise SrcStreamClosedError(self, detail="send response failed {0}".format(
                _wrap_req_path(self.context, self.req)))

    def on_info_response(self, response):
        plugin_result = self.interceptor.response(
            layer_context=self.context,
            request=self.req, response=response)
        self.resp = plugin_result.response if plugin_result else response

    def finished(self):
        return (self.switch_protocol or
                self.src_stream.closed() or
                (self.dest_stream and self.dest_stream.closed()))

    def finish(self, switch_protocol=False):
        self.interceptor.publish(
            layer_context=self.context,
            request=self.req, response=self.resp)
        if self.context.mode == "replay":
            self.src_stream.close()
            self.dest_stream.close()
        elif switch_protocol:
            self.switch_protocol = True
        elif self.src_conn.closed() or self.dest_conn.closed():
            self.src_stream.close()
            self.dest_stream.close()
        else:
            self.src_conn.start_next_cycle()
            self.dest_conn.start_next_cycle()

    @gen.coroutine
    def handle_http_proxy(self):
        if self.is_tunnel_http_proxy():
            logger.debug("proxy tunnel to {0}".format(self.req.path))
            scheme, host, port = parse_proxy_path(self.req.path)
            yield self.connect_to_dest(scheme, (host, port))
            self.src_conn.send_response(HttpResponse(
                code="200",
                reason="OK", version="HTTP/1.1"))
            raise SwitchToTunnelHttpProxy
        elif self.is_normal_http_proxy():
            logger.debug("proxy to {0}".format(self.req.path))
            scheme, host, port = parse_proxy_path(self.req.path)
            yield self.connect_to_dest(scheme, (host, port))
            self.dest_conn.io_stream = self.dest_stream
        else:
            raise gen.Return(None)

    def is_tunnel_http_proxy(self):
        return self.req.method == "CONNECT"

    def is_normal_http_proxy(self):
        return (self.req.path.startswith("http://") or
                self.req.path.startswith("https://"))

    @gen.coroutine
    def connect_to_dest(self, scheme, addr):
        if addr != (self.context.host, self.context.port):
            logger.debug("proxy to new connection {0}".format(addr))
            if self.dest_stream:
                self.dest_stream.close()

            dest_stream = yield self.create_dest_stream(addr)
            self.context.dest_stream = dest_stream
            self.context.scheme = scheme
            self.context.host = addr[0]
            self.context.port = addr[1]
            logger.debug("proxy to new connection success".format(addr))
        else:
            logger.debug("proxy to same connection")


class SwitchToTunnelHttpProxy(Exception):
    pass
