import os
from tornado.iostream import PipeIOStream
from tornado import gen

import h11

from microproxy.protocol.http1 import Connection as Http1Connection
from microproxy.utils import get_logger
from microproxy.context import ViewerContext, LayerContext
from microproxy.config import Config

logger = get_logger(__name__)


class ReplayHandler(object):
    def __init__(self, config, proxy_server):
        config_dict = dict(config)
        config_dict.update(dict(mode="replay"))
        self.config = Config(config_dict)
        self.proxy_server = proxy_server

    @gen.coroutine
    def handle(self, event):
        logger.debug("start handling replay event")
        try:
            viewer_context = ViewerContext(**event)
            write_stream, read_stream = self._create_streams()

            self._send_http1_request(write_stream, viewer_context)
            layer_context = LayerContext(
                src_stream=read_stream,
                host=viewer_context.host,
                port=viewer_context.port,
                config=self.config,
                scheme=viewer_context.scheme)
            yield self.proxy_server.layer_manager.run_layers(
                read_stream, context=layer_context)
        except Exception as e:
            logger.exception(e)
        else:
            logger.debug("replay event successfully")

    def _create_streams(self):
        read_fd, write_fd = os.pipe()
        write_stream = PipeIOStream(write_fd, io_loop=self.proxy_server.io_loop)
        read_stream = PipeIOStream(read_fd, io_loop=self.proxy_server.io_loop)
        return (write_stream, read_stream)

    def _send_http1_request(self, stream, context):
        Http1Connection(h11.CLIENT, stream).send_request(context.request)
