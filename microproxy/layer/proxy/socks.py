import errno

from tornado import gen
from tornado import iostream
from socks5 import GreetingResponse, Response
from socks5 import RESP_STATUS, AUTH_TYPE, REQ_COMMAND, ADDR_TYPE
from socks5 import Connection

from microproxy.layer.base import ProxyLayer
from microproxy.exception import SrcStreamClosedError, DestNotConnectedError, ProtocolError

from microproxy.log import ProxyLogger
logger = ProxyLogger.get_logger(__name__)


class SocksLayer(ProxyLayer):
    def __init__(self, context):
        super(SocksLayer, self).__init__(context)
        self.socks_conn = Connection(our_role="server")

    @gen.coroutine
    def process_and_return_context(self):
        self.socks_conn.initiate_connection()
        while True:
            try:
                data = yield self.context.src_stream.read_bytes(1024, partial=True)
            except iostream.StreamClosedError:
                raise SrcStreamClosedError(
                    detail="client closed while socks handshaking")

            _event = self.socks_conn.recv(data)
            if _event == "GreetingRequest":
                yield self.handle_greeting_request(_event)
            elif _event == "Request":
                dest_stream, host, port = yield self.handle_request_and_create_destination(_event)
                self.context.dest_stream = dest_stream
                self.context.host = host
                self.context.port = port
                break
            else:
                raise NotImplementedError("not handling with {0}".format(_event))

        raise gen.Return(self.context)

    @gen.coroutine
    def handle_greeting_request(self, event):
        if not AUTH_TYPE["NO_AUTH"] in event.methods:
            yield self.send_event_to_src_conn(
                GreetingResponse(AUTH_TYPE["NO_SUPPORT_AUTH_METHOD"]))
        else:
            yield self.send_event_to_src_conn(
                GreetingResponse(AUTH_TYPE["NO_AUTH"]))

    @gen.coroutine
    def handle_request_and_create_destination(self, event):
        """Handle the socks request from source
        Create destination connection

        Returns:
            tuple: (dest_stream, host, port)
        """
        if event.cmd != REQ_COMMAND["CONNECT"]:
            logger.debug("Unsupport connect type")
            yield self.send_event_to_src_conn(Response(
                RESP_STATUS["COMMAND_NOT_SUPPORTED"],
                event.atyp, event.addr, event.port), raise_exception=False)
            raise ProtocolError("Unsupport bind type")

        try:
            dest_stream = yield self.create_dest_stream((str(event.addr), event.port))
        except gen.TimeoutError as e:
            yield self.handle_timeout_error(e, event)
        except iostream.StreamClosedError as e:
            yield self.handle_stream_closed_error(e, event)
        else:
            yield self.send_event_to_src_conn(Response(
                RESP_STATUS["SUCCESS"],
                event.atyp, event.addr, event.port))
            raise gen.Return((dest_stream, event.addr, event.port))

    @gen.coroutine
    def send_event_to_src_conn(self, event, raise_exception=True):
        try:
            data = self.socks_conn.send(event)
            yield self.context.src_stream.write(data)
        except iostream.StreamClosedError as e:  # pragma: no cover
            if raise_exception:
                raise SrcStreamClosedError(detail="failed on {0}".format(type(event).__name__))
            logger.error("stream closed on {0}".format(type(event)))
        except Exception as e:  # pragma: no cover
            if raise_exception:
                raise
            logger.exception(e)

    @gen.coroutine
    def handle_timeout_error(self, error, event):
        logger.debug("connection timout {0}:{1}".format(
            event.addr, event.port))
        yield self.send_event_to_src_conn(Response(
            RESP_STATUS["NETWORK_UNREACHABLE"],
            event.atyp, event.addr, event.port), raise_exception=False)
        raise DestNotConnectedError((event.addr, event.port))

    @gen.coroutine
    def handle_stream_closed_error(self, error, event):
        if error.real_error:
            err_num = abs(error.real_error[0])
            try:
                errorcode = errno.errorcode[err_num]
            except KeyError:
                errorcode = "undefined(code={0})".format(err_num)

            logger.debug("connect to {0}:{1} with error code {2}".format(
                event.addr, event.port, errorcode))
            # NOTE: if we submit an incorrect address type,
            # the error code will be:
            # - ENOEXEC in macos.
            # - EBADF in linux.
            if err_num in (errno.ENOEXEC, errno.EBADF):
                reason = "ADDRESS_TYPE_NOT_SUPPORTED"
            elif err_num == errno.ETIMEDOUT:
                reason = "NETWORK_UNREACHABLE"
            else:
                logger.error("unhandled error code {0} received".format(errorcode))
                reason = "GENRAL_FAILURE"

            yield self.send_event_to_src_conn(Response(
                RESP_STATUS[reason],
                event.atyp, event.addr, event.port), raise_exception=False)
            raise DestNotConnectedError((event.addr, event.port))
        else:  # pragma: no cover
            # TODO: StreamClosedError without real_error?
            # need check that tornado would occur this situation?
            raise
