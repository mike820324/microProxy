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
                data = self.socks_conn.send(event)
                yield self.context.src_stream.write(data)

                if error:
                    raise error

                break
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
        try:
            dest_stream = yield self.create_dest_stream((host, port))

        except gen.TimeoutError as e:
            logger.debug("connection timout {0}:{1}".format(
                host, port))
            response_event = Response(
                socks_version, RESP_STATUS["NETWORK_UNREACHABLE"],
                event.atyp, event.addr, event.port)

            error = DestNotConnectedError(e)
            raise gen.Return((error, response_event))

        except iostream.StreamClosedError as e:
            if e.real_error:
                err_num = abs(e.real_error[0])
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
                    logger.error("unhandle error code {0} received".format(
                        errno.errorcode[err_num]))
                    response_event = Response(
                        socks_version, RESP_STATUS["GENRAL_FAILURE"],
                        event.atyp, event.addr, event.port)
                error = DestNotConnectedError(e)
                raise gen.Return((error, response_event))
            else:
                # NOTE: if real_error is None, it imply the source stream is closed.
                dest_stream.close()
                raise SrcStreamClosedError(e)

        self.context.dest_stream = dest_stream
        self.context.host = host
        self.context.port = port

        error = None
        response_event = Response(
            socks_version, RESP_STATUS["SUCCESS"],
            event.atyp, event.addr, event.port)

        raise gen.Return((None, response_event))
