from __future__ import absolute_import

from tornado import gen
from tornado import iostream

from microproxy.exception import DestStreamClosedError, SrcStreamClosedError, DestNotConnectedError
from microproxy.layer import (
    SocksLayer, TransparentLayer, ReplayLayer, HttpProxyLayer,
    ForwardLayer, TlsLayer, Http1Layer, Http2Layer
)

from microproxy.log import ProxyLogger
logger = ProxyLogger.get_logger(__name__)


def get_first_layer(context):
    mode = context.mode
    if mode == "socks":
        return SocksLayer(context)
    elif mode == "transparent":
        return TransparentLayer(context)
    elif mode == "replay":
        return ReplayLayer(context)
    elif mode == "http":
        return HttpProxyLayer(context)
    else:
        raise ValueError("Unsupport proxy mode: {0}".format(mode))


@gen.coroutine
def run_layers(server_state, initial_layer, initial_layer_context):  # pragma: no cover
    current_context = initial_layer_context
    current_layer = initial_layer

    try:
        while current_layer:
            logger.debug("Enter {0} Layer".format(current_layer))
            current_context = yield current_layer.process_and_return_context()
            logger.debug("Leave {0} Layer".format(current_layer))
            current_layer = _next_layer(server_state, current_layer, current_context)
    except Exception as error:
        _handle_layer_error(error, current_context)

    raise gen.Return(None)


def _handle_layer_error(error, layer_context):
    if isinstance(error, gen.TimeoutError):
        layer_context.src_stream.close()
        return

    if isinstance(error, DestNotConnectedError):
        logger.debug("destination not conected")
        return

    if isinstance(error, DestStreamClosedError):
        logger.error(error)
        layer_context.src_stream.close()
        return

    if isinstance(error, SrcStreamClosedError):
        logger.error(error)
        return

    if isinstance(error, iostream.StreamClosedError):
        logger.error("stream closed")
        # NOTE: unhandled StreamClosedError, print stack to find out where
        logger.exception(error)
        layer_context.src_stream.close()
        return

    raise


def _next_layer(server_state, current_layer, context):
    config = server_state.config
    http_ports = [80] + config["http_port"]
    https_ports = [443] + config["https_port"]

    if isinstance(current_layer, HttpProxyLayer):
        return Http1Layer(server_state, context)

    if isinstance(current_layer, (SocksLayer, TransparentLayer)):
        if context.port in http_ports:
            context.scheme = "http"
            return Http1Layer(server_state, context)
        elif context.port in https_ports:
            return TlsLayer(server_state, context)
        else:
            return ForwardLayer(server_state, context)

    if isinstance(current_layer, TlsLayer):
        if context.scheme == "https":
            return Http1Layer(server_state, context)
        elif context.scheme == "h2":
            return Http2Layer(server_state, context)
        else:
            return ForwardLayer(server_state, context)

    if isinstance(current_layer, ReplayLayer):
        if context.scheme in ("http", "https"):
            return Http1Layer(server_state, context)
        elif context.scheme == "h2":
            return Http2Layer(server_state, context)
        else:
            return ForwardLayer(server_state, context)

    if isinstance(current_layer, Http1Layer):
        if context.scheme == "websocket":
            return ForwardLayer(server_state, context)
        elif context.scheme == "https" and not context.done:
            return TlsLayer(server_state, context)
        elif context.scheme == "http" and not context.done:
            return Http1Layer(server_state, context)
