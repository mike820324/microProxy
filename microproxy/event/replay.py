import os
from tornado.iostream import PipeIOStream
from tornado import gen

import h11
from h11 import Connection as H11Connection

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

            self._make_h11_request(write_stream, viewer_context)
            layer_context = LayerContext(
                src_stream=read_stream,
                host=viewer_context.host,
                port=viewer_context.port,
                config=self.config)
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

    def _make_h11_request(self, stream, context):
        conn = H11Connection(our_role=h11.CLIENT)
        stream.write(conn.send(
            h11.Request(
                method=context.request.method,
                target=context.path,
                headers=context.request.headers.get_list())))
        if context.request.body:
            stream.write(conn.send(
                h11.Data(data=context.request.body.decode("base64"))))
        stream.write(conn.send(
            h11.EndOfMessage()))
