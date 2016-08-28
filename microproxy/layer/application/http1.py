from tornado import concurrent

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
            on_response=self.on_response)
        self._future = concurrent.Future()
        self.req = None
        self.resp = None

    def process_and_return_context(self):
        self.context.src_stream.read_until_close(
            streaming_callback=self.src_conn.receive)
        self.context.src_stream.set_close_callback(self.on_src_close)

        self.context.dest_stream.read_until_close(
            streaming_callback=self.dest_conn.receive)
        self.context.dest_stream.set_close_callback(self.on_dest_close)
        return self._future

    def on_src_close(self):
        logger.debug("source connection is closed")
        self.context.dest_stream.close()
        if self._future.running():
            if self.req or self.resp:  # contains running request
                self._future.set_exception(SrcStreamClosedError())
            else:
                self._future.set_result(self.context)

    def on_dest_close(self):
        logger.debug("destination connection is closed")
        self.context.src_stream.close()
        if self._future.running():
            if self.req or self.resp:  # contains running request
                self._future.set_exception(DestStreamClosedError())
            else:
                self._future.set_result(self.context)

    def on_request(self, request):
        plugin_result = self.context.interceptor.request(
            layer_context=self.context, request=request)

        self.req = plugin_result if plugin_result else request
        self.dest_conn.send_request(self.req)

    def on_response(self, response):
        plugin_result = self.context.interceptor.response(
            layer_context=self.context,
            request=self.req, response=response)

        self.resp = plugin_result if plugin_result else response
        self.src_conn.send_response(self.resp)
        self.finish()

    def finish(self):
        self.context.interceptor.publish(
            layer_context=self.context,
            request=self.req, response=self.resp)
        self.req = None
        self.resp = None
        if self.context.config["mode"] == "replay":
            self.context.src_stream.close()
            self.context.dest_stream.close()
        else:
            self.src_conn.start_next_cycle()
            self.dest_conn.start_next_cycle()
