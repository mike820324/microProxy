import os
from tornado.iostream import PipeIOStream
from tornado import gen

import h11
from microproxy.protocol.http1 import Connection as Http1Connection
from microproxy.protocol.http2 import Connection as Http2Connection
from microproxy.utils import get_logger, curr_loop
from microproxy.context import ViewerContext, LayerContext
from microproxy.config import Config
from microproxy import layer_manager
from microproxy.interceptor import get_interceptor

logger = get_logger(__name__)


class ReplayHandler(object):
    def __init__(self, config):
        config_dict = dict(config)
        config_dict.update(dict(mode="replay"))
        self.config = Config(config_dict)
        self.layer_manager = layer_manager

    @gen.coroutine
    def handle(self, event):
        logger.debug("start handling replay event")
        try:
            viewer_context = ViewerContext(**event)
            write_stream, read_stream = self._create_streams()

            if viewer_context.scheme in ("http", "https"):
                self._send_http1_request(write_stream, viewer_context)
            elif viewer_context.scheme == "h2":
                self._send_http2_request(write_stream, viewer_context)
            else:
                raise ValueError("not support replay with: {0}".format(
                    viewer_context.scheme))

            layer_context = LayerContext(
                src_stream=read_stream,
                host=viewer_context.host,
                port=viewer_context.port,
                config=self.config,
                scheme=viewer_context.scheme,
                interceptor=get_interceptor())
            yield self.layer_manager.run_layers(layer_context)
        except Exception as e:
            logger.exception(e)
        else:
            logger.debug("replay event successfully")

    def _create_streams(self):
        read_fd, write_fd = os.pipe()
        io_loop = curr_loop()
        write_stream = PipeIOStream(write_fd, io_loop=io_loop)
        read_stream = PipeIOStream(read_fd, io_loop=io_loop)
        return (write_stream, read_stream)

    def _send_http1_request(self, stream, context):
        Http1Connection(h11.CLIENT, stream).send_request(context.request)

    def _send_http2_request(self, stream, context):
        conn = Http2Connection(stream, client_side=True)
        conn.initiate_connection()
        stream_id = conn.get_next_available_stream_id()
        conn.send_request(stream_id, context.request)
