import h11
from h11 import Connection as H11Connection
from h11 import (
    Request, InformationalResponse, Response, Data, EndOfMessage,
    ConnectionClosed)

from tornado import gen

from microproxy.context import HttpRequest, HttpResponse
from microproxy.exception import ProtocolError
from microproxy.utils import get_logger
logger = get_logger(__name__)


class Connection(H11Connection):
    def __init__(self, our_role, io_stream, conn_type=None,
                 readonly=False, on_request=None, on_response=None,
                 on_info_response=None, on_unhandled=None, **kwargs):
        super(Connection, self).__init__(our_role, **kwargs)
        on_unhandled = on_unhandled or self._default_on_unhandled
        self.io_stream = io_stream
        self.conn_type = conn_type or str(our_role)
        self.readonly = readonly
        self.on_request = on_request or on_unhandled
        self.on_response = on_response or on_unhandled
        self.on_info_response = on_info_response or on_unhandled
        self._req = None
        self._resp = None
        self._body_chunks = []
        self.unhandled_events = None

    def send(self, event):
        logger.debug("event send to {0}: {1}".format(self.conn_type, type(event)))
        data = super(Connection, self).send(event)
        if not self.readonly:
            self.io_stream.write(data)

    @gen.coroutine
    def read_bytes(self):
        data = yield self.io_stream.read_bytes(
            self.io_stream.max_buffer_size, partial=True)
        self.receive(data)

    def receive(self, data, raise_exception=False):
        try:
            logger.debug("data received from {0} with length {1}".format(self.conn_type, len(data)))
            self.receive_data(data)
            while True:
                event = self.next_event()
                self._log_event(event)
                if isinstance(event, Request):
                    if self._req:  # pragma: no cover
                        # NOTE: guess that never happen because h11 should help us handle http state
                        raise ProtocolError("http1 connection had received request")
                    self._req = event
                elif isinstance(event, InformationalResponse):
                    self.on_info_response(HttpResponse(
                        version=self._parse_version(event),
                        reason=event.reason,
                        code=str(event.status_code),
                        headers=event.headers))
                elif isinstance(event, Response):
                    self._resp = event
                elif isinstance(event, Data):
                    self._body_chunks.append(bytes(event.data))
                elif isinstance(event, EndOfMessage):
                    if self.our_role is h11.SERVER:
                        if not self._req:  # pragma: no cover
                            # NOTE: guess that never happen because h11 should help us handle http state
                            raise ProtocolError("EndOfMessage received, but not request found")
                        self.on_request(HttpRequest(
                            version=self._parse_version(self._req),
                            method=self._req.method,
                            path=self._req.target,
                            headers=self._req.headers,
                            body=b"".join(self._body_chunks)))
                    else:
                        if not self._resp:  # pragma: no cover
                            # NOTE: guess that never happen because h11 should help us handle http state
                            raise ProtocolError("EndOfMessage received, but not response found")
                        self.on_response(HttpResponse(
                            version=self._parse_version(self._resp),
                            reason=self._resp.reason,
                            code=str(self._resp.status_code),
                            headers=self._resp.headers,
                            body=b"".join(self._body_chunks)))
                    self._cleanup_after_received()
                    break
                elif isinstance(event, ConnectionClosed):  # pragma: no cover
                    raise ProtocolError("Should closed the connection")
                elif event is h11.NEED_DATA:
                    break
                elif event is h11.PAUSED:  # pragma: no cover
                    break
                else:  # pragma: no cover
                    logger.warning("event recevied was not handled from {0}: {1}".format(self.conn_type, repr(event)))
        except Exception as e:  # pragma: no cover
            if raise_exception:
                raise
            logger.error("Exception on {0}".format(self.conn_type))
            logger.exception(e)

    def _log_event(self, event):
        if isinstance(event, Data):  # Note: Data event that would print to mush info
            logger.debug("event recevied from {0}: {1}".format(self.conn_type, type(event)))
        else:
            logger.debug("event recevied from {0}: {1}".format(self.conn_type, repr(event)))

    def _parse_version(self, http_content):
        try:
            return "HTTP/{0}".format(http_content.http_version)
        except:
            return "HTTP/1.1"

    def _cleanup_after_received(self):
        self._req = None
        self._resp = None
        self._body_chunks = []
        if self.our_state is h11.MUST_CLOSE:
            self.io_stream.close()

    def send_request(self, request):
        self.send(h11.Request(
            method=request.method,
            target=request.path,
            headers=request.headers,
            keep_case=True))
        if request.body:
            self.send(h11.Data(data=request.body))
        self.send(h11.EndOfMessage())

    def send_response(self, response):
        self.send(h11.Response(
            status_code=int(response.code),
            reason=response.reason,
            headers=response.headers,
            keep_case=True))
        if response.body:
            self.send(h11.Data(data=response.body))
        self.send(h11.EndOfMessage())
        if self.our_state is h11.MUST_CLOSE:
            self.io_stream.close()

    def send_info_response(self, response):
        self.send(h11.InformationalResponse(
            status_code=int(response.code),
            headers=response.headers,
            reason=response.reason,
            keep_case=True))

    def _default_on_unhandled(self, *args):  # pragma: no cover
        logger.warn("unhandled event: {0}".format(args))
        self.unhandled_events.append(args)

    def closed(self):
        return self.our_state is h11.MUST_CLOSE or self.io_stream.closed()
