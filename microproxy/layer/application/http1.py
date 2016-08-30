from tornado import concurrent, gen
from tornado.iostream import StreamClosedError
import h11

from microproxy.protocol.http1 import Connection
from microproxy.exception import SrcStreamClosedError, DestStreamClosedError
from microproxy.utils import get_logger
logger = get_logger(__name__)


class Http1Layer(object):
    def __init__(self, context):
        super(Http1Layer, self).__init__()
        self.context = context
        self.src_conn = Connection(
            h11.SERVER,
            self.context.src_stream,
            conn_type="src",
            readonly=context.config["mode"] == "replay",
            on_request=self.on_request)
        self.dest_conn = Connection(
            h11.CLIENT,
            self.context.dest_stream,
            conn_type="dest",
            on_response=self.on_response,
            on_info_response=self.on_info_response)
        self._future = concurrent.Future()
        self.req = None
        self.resp = None

    @gen.coroutine
    def process_and_return_context(self):
        try:
            yield self.run_first_request()
        except StreamClosedError:
            self.context.src_stream.close()
            self.context.dest_stream.close()
            raise
        else:
            if self._future.running():
                self.context.src_stream.read_until_close(
                    streaming_callback=self.src_conn.receive)
                self.context.src_stream.set_close_callback(self.on_src_close)

                self.context.dest_stream.read_until_close(
                    streaming_callback=self.dest_conn.receive)
                self.context.dest_stream.set_close_callback(self.on_dest_close)
            context = yield self._future
            raise gen.Return(context)

    @gen.coroutine
    def run_first_request(self):
        # NOTE: run first request to handle protocol change
        while not self.req:
            try:
                data = yield self.context.src_stream.read_bytes(
                    self.context.src_stream.max_buffer_size, partial=True)
            except StreamClosedError:
                raise SrcStreamClosedError
            else:
                self.src_conn.receive(data, raise_exception=True)

        while not self.resp:
            try:
                data = yield self.context.dest_stream.read_bytes(
                    self.context.dest_stream.max_buffer_size, partial=True)
            except StreamClosedError:
                raise DestStreamClosedError
            else:
                self.dest_conn.receive(data, raise_exception=True)

        if self.is_websocket():
            self.context.scheme = "websocket"
            self._future.set_result(self.context)
        raise gen.Return(None)

    def on_src_close(self):
        logger.debug("source connection is closed")
        self.context.dest_stream.close()
        if self._future.running():
            self._future.set_result(self.context)

    def on_dest_close(self):
        logger.debug("destination connection is closed")
        self.context.src_stream.close()
        if self._future.running():
            self._future.set_result(self.context)

    def on_request(self, request):
        plugin_result = self.context.interceptor.request(
            layer_context=self.context, request=request)

        self.req = plugin_result.request if plugin_result else request
        try:
            self.dest_conn.send_request(self.req)
        except StreamClosedError:
            raise DestStreamClosedError

    def on_response(self, response):
        plugin_result = self.context.interceptor.response(
            layer_context=self.context,
            request=self.req, response=response)

        self.resp = plugin_result.response if plugin_result else response
        try:
            self.src_conn.send_response(self.resp)
        except StreamClosedError:
            raise SrcStreamClosedError

        self.finish()

    def on_info_response(self, response):
        plugin_result = self.context.interceptor.response(
            layer_context=self.context,
            request=self.req, response=response)
        self.resp = plugin_result.response if plugin_result else response
        self.src_conn.send_info_response(self.resp)
        self.finish(switch_protocol=True)

    def is_websocket(self):
        return (("Upgrade", "websocket") in self.req.headers.get_list() and
                ("Upgrade", "websocket") in self.resp.headers.get_list())

    def finish(self, switch_protocol=False):
        self.context.interceptor.publish(
            layer_context=self.context,
            request=self.req, response=self.resp)
        if self.context.config["mode"] == "replay":
            self.context.src_stream.close()
            self.context.dest_stream.close()
        elif switch_protocol:
            pass
        else:
            self.src_conn.start_next_cycle()
            self.dest_conn.start_next_cycle()
