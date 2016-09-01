import errno

from tornado import gen
from tornado import iostream
from socks5 import GreetingRequest, Request
from socks5 import GreetingResponse, Response
from socks5 import VERSION as socks_version
from socks5 import RESP_STATUS, AUTH_TYPE, REQ_COMMAND
from socks5.connection import ServerConnection

from base import ProxyLayer

from microproxy.utils import get_logger
from microproxy.exception import SrcStreamClosedError, DestNotConnectedError, ProtocolError

logger = get_logger(__name__)


class SocksLayer(ProxyLayer):
    def __init__(self, context):
        super(SocksLayer, self).__init__(context)
        self.socks_conn = ServerConnection()

    @gen.coroutine
    def process_and_return_context(self):
        self.socks_conn.initiate_connection()
        while True:
            data = yield self.context.src_stream.read_bytes(1024, partial=True)
            _event = self.socks_conn.receive(data)

            if isinstance(_event, GreetingRequest):
                event = self.handle_greeting_request(_event)
                data = self.socks_conn.send(event)
                yield self.context.src_stream.write(data)

            elif isinstance(_event, Request):
                error, event = yield self.handle_request(_event)
                if event:
                    data = self.socks_conn.send(event)
                    yield self.context.src_stream.write(data)

                if error:
                    raise error

                break
        self.context.src_stream.pause()
        raise gen.Return(self.context)

    def handle_greeting_request(self, event):
        if not AUTH_TYPE["NO_AUTH"] in event.methods:
            response_event = GreetingResponse(
                socks_version, AUTH_TYPE["NO_SUPPORT_AUTH_METHOD"])
        else:
            response_event = GreetingResponse(
                socks_version, AUTH_TYPE["NO_AUTH"])
        return response_event

    @gen.coroutine
    def handle_request(self, event):

        if event.cmd != REQ_COMMAND["CONNECT"]:
            logger.debug("Unsupport connect type")
            error = ProtocolError("Unsupport bind type")
            response_event = Response(
                socks_version, RESP_STATUS["COMMAND_NOT_SUPPORTED"],
                event.atyp, event.addr, event.port)
            raise gen.Return((error, response_event))

        host = event.addr
        port = event.port
        dest_stream = None
        try:
            dest_stream = yield self.create_dest_stream((host, port))

        except Exception as e:
            err, response_event = self.handle_connection_error(
                e, event, dest_stream)

        else:
            self.context.dest_stream = dest_stream
            self.context.host = host
            self.context.port = port
            err = None
            response_event = Response(
                socks_version, RESP_STATUS["SUCCESS"],
                event.atyp, event.addr, event.port)

        raise gen.Return((err, response_event))

    def handle_connection_error(self, error, event, dest_stream):
        host = event.addr
        port = event.port

        if isinstance(error, gen.TimeoutError):
            logger.debug("connection timout {0}:{1}".format(
                host, port))
            response_event = Response(
                socks_version, RESP_STATUS["NETWORK_UNREACHABLE"],
                event.atyp, event.addr, event.port)

            error = DestNotConnectedError(error)
            return (error, response_event)

        if isinstance(error, iostream.StreamClosedError):
            e = error
            if e.real_error:
                err_num = abs(e.real_error[0])
                try:
                    logger.debug("connect to {0}:{1} with error code {2}".format(
                        host, port, errno.errorcode[err_num]))

                    # NOTE: if we submit an incorrect address type,
                    # the error code will be:
                    # - ENOEXEC in macos.
                    # - EBADF in linux.
                    if err_num == errno.ENOEXEC or err_num == errno.EBADF:
                        response_event = Response(
                            socks_version,
                            RESP_STATUS["ADDRESS_TYPE_NOT_SUPPORTED"],
                            event.atyp, event.addr, event.port)

                    elif err_num == errno.ETIMEDOUT:
                        response_event = Response(
                            socks_version, RESP_STATUS["NETWORK_UNREACHABLE"],
                            event.atyp, event.addr, event.port)

                    else:
                        logger.error("unhandled error code {0} received".format(errno.errorcode[err_num]))
                        response_event = Response(
                            socks_version, RESP_STATUS["GENRAL_FAILURE"],
                            event.atyp, event.addr, event.port)

                except KeyError:
                    logger.error("unknown error code {0} received".format(err_num))
                    response_event = Response(
                        socks_version, RESP_STATUS["GENRAL_FAILURE"],
                        event.atyp, event.addr, event.port)

                error = DestNotConnectedError(e)
                return (error, response_event)
            else:
                # NOTE: if real_error is None, it imply the source stream is closed.
                if dest_stream:
                    dest_stream.close()
                return (SrcStreamClosedError(e), None)

        # NOTE: Unhandle exception type, raise it
        else:
            raise error
