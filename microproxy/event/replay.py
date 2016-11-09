import os
from tornado.iostream import PipeIOStream
from tornado import gen

import h11
from microproxy.protocol.http1 import Connection as Http1Connection
from microproxy.protocol.http2 import Connection as Http2Connection
from microproxy.utils import get_logger, curr_loop
from microproxy.context import ViewerContext, LayerContext
from microproxy.layer import manager as default_layer_manager

logger = get_logger(__name__)


class ReplayHandler(object):
    def __init__(self, server_state, layer_manager=None, io_loop=None):
        self.server_state = server_state
        self.io_loop = io_loop or curr_loop()
        self.layer_manager = layer_manager or default_layer_manager

    @gen.coroutine
    def handle(self, event):
        logger.debug("start handling replay event")
        try:
            viewer_context = ViewerContext.deserialize(event.context)
            write_stream, read_stream = self._create_streams()

            if viewer_context.scheme in ("http", "https"):
                self._send_http1_request(write_stream, viewer_context)
            elif viewer_context.scheme == "h2":
                self._send_http2_request(write_stream, viewer_context)
            else:
                raise ValueError("not support replay with: {0}".format(
                    viewer_context.scheme))

            layer_context = LayerContext(
                mode="replay",
                src_stream=read_stream,
                host=viewer_context.host,
                port=viewer_context.port,
                scheme=viewer_context.scheme)

            initial_layer = self.layer_manager.get_first_layer(layer_context)
            yield self.layer_manager.run_layers(
                self.server_state, initial_layer, layer_context)
        except Exception as e:
            logger.exception(e)
        else:
            logger.debug("replay event successfully")

    def _create_streams(self):
        read_fd, write_fd = os.pipe()
        write_stream = PipeIOStream(write_fd, io_loop=self.io_loop)
        read_stream = PipeIOStream(read_fd, io_loop=self.io_loop)
        return (write_stream, read_stream)

    def _send_http1_request(self, stream, context):
        logger.debug("replay http1 request: {0}".format(context.request))
        Http1Connection(h11.CLIENT, stream).send_request(context.request)

    def _send_http2_request(self, stream, context):
        logger.debug("replay http2 request: {0}".format(context.request))
        conn = Http2Connection(stream, client_side=True)
        conn.initiate_connection()
        stream_id = conn.get_next_available_stream_id()
        conn.send_request(stream_id, context.request)
