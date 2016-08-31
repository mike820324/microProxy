from tornado import gen
from tornado import iostream

from microproxy.iostream import safe_resume_stream
from microproxy.utils import get_logger
from microproxy.exception import DestStreamClosedError, SrcStreamClosedError, DestNotConnectedError
from microproxy.layer import SocksLayer, TransparentLayer, ReplayLayer
from microproxy.layer import ForwardLayer, TlsLayer, Http1Layer, Http2Layer

logger = get_logger(__name__)


@gen.coroutine
def run_layers(initial_layer_context):
    current_layer = _get_first_layer(initial_layer_context)
    src_stream = initial_layer_context.src_stream

    while current_layer:
        try:
            logger.debug("Enter {0} Layer".format(current_layer))
            current_context = yield current_layer.process_and_return_context()
            logger.debug("Leave {0} Layer".format(current_layer))
            current_layer = _next_layer(current_layer, current_context)
        except gen.TimeoutError:
            src_stream.close()
            break
        except DestNotConnectedError:
            logger.debug("destination not conected")
            break
        except DestStreamClosedError:
            logger.error("destination stream closed unexceptedly")
            src_stream.close()
            break
        except SrcStreamClosedError:
            logger.error("source stream closed unexceptedly")
            break
        except iostream.StreamClosedError:
            logger.error("stream closed")
            src_stream.close()
            break
        except Exception:
            raise

    raise gen.Return(None)


def _get_first_layer(context):
    mode = context.config["mode"]
    if mode == "socks":
        return SocksLayer(context)
    elif mode == "transparent":
        return TransparentLayer(context)
    elif mode == "replay":
        return ReplayLayer(context)
    else:
        raise ValueError("Unsupport proxy mode: {0}".format(mode))


def _next_layer(current_layer, context):
    http_ports = [80] + context.config["http_port"]
    https_ports = [443] + context.config["https_port"]

    if isinstance(current_layer, (SocksLayer, TransparentLayer)):
        safe_resume_stream(context.src_stream)
        if context.port in http_ports:
            context.scheme = "http"
            return Http1Layer(context)
        elif context.port in https_ports:
            return TlsLayer(context)
        else:
            return ForwardLayer(context)

    if isinstance(current_layer, TlsLayer):
        if context.scheme == "https":
            return Http1Layer(context)
        elif context.scheme == "h2":
            return Http2Layer(context)
        else:
            return ForwardLayer(context)

    if isinstance(current_layer, ReplayLayer):
        if context.scheme in ("http", "https"):
            return Http1Layer(context)
        elif context.scheme == "h2":
            return Http2Layer(context)
        else:
            return ForwardLayer(context)
