import h11
from h11 import Connection as H11Connection
from h11 import (
    Request, InformationalResponse, Response, Data, EndOfMessage,
    ConnectionClosed)

from microproxy.context import HttpRequest, HttpResponse
from microproxy.utils import get_logger
logger = get_logger(__name__)


class Connection(H11Connection):
    def __init__(self, our_role, io_stream, conn_type=None,
                 readonly=False, on_request=None, on_response=None,
                 on_info_response=None, **kwargs):
        super(Connection, self).__init__(our_role, **kwargs)
        self.io_stream = io_stream
        self.conn_type = conn_type or str(our_role)
        self.readonly = readonly
        self.on_request = on_request
        self.on_response = on_response
        self.on_info_response = on_info_response
        self._req = None
        self._resp = None
        self._body_chunks = []

    def send(self, event):
        logger.debug("event send to {0}: {1}".format(self.conn_type, type(event)))
        data = super(Connection, self).send(event)
        if not self.readonly:
            self.io_stream.write(data)

    def receive(self, data, raise_exception=False):
        try:
            logger.debug("data received from {0} with length {1}".format(self.conn_type, len(data)))
            self.receive_data(data)
            while True:
                event = self.next_event()
                self._log_event(event)
                if isinstance(event, Request):
                    if self._req:
                        raise RuntimeError("http1 connection had received request")
                    self._req = event
                elif isinstance(event, InformationalResponse):
                    self.on_info_response(HttpResponse(
                        version=self._parse_version(event),
                        reason=event.reason,
                        code=event.status_code,
                        headers=event.headers))
                elif isinstance(event, Response):
                    self._resp = event
                elif isinstance(event, Data):
                    self._body_chunks.append(bytes(event.data))
                elif isinstance(event, EndOfMessage):
                    if self.our_role is h11.SERVER:
                        if not self._req:
                            raise RuntimeError("EndOfMessage received, but not request found")
                        self.on_request(HttpRequest(
                            version=self._parse_version(self._req),
                            method=self._req.method,
                            path=self._req.target,
                            headers=self._req.headers,
                            body=b"".join(self._body_chunks)))
                    else:
                        if not self._resp:
                            raise RuntimeError("EndOfMessage received, but not response found")
                        self.on_response(HttpResponse(
                            version=self._parse_version(self._resp),
                            reason=self._resp.reason,
                            code=self._resp.status_code,
                            headers=self._resp.headers,
                            body=b"".join(self._body_chunks)))
                    self._req = None
                    self._resp = None
                    self._body_chunks = []
                elif isinstance(event, ConnectionClosed):
                    self.io_stream.close()
                    break
                elif event is h11.NEED_DATA:
                    break
                elif event is h11.PAUSED:
                    break
                else:
                    logger.warning("event recevied was not handled from {0}: {1}".format(self.conn_type, repr(event)))
        except Exception as e:
            if raise_exception:
                raise e
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

    def send_request(self, request):
        self.send(h11.Request(
            method=request.method,
            target=request.path,
            headers=request.headers.get_list()))
        if request.body:
            self.send(h11.Data(data=request.body))
        self.send(h11.EndOfMessage())

    def send_response(self, response):
        self.send(h11.Response(
            status_code=response.code,
            headers=response.headers.get_list(),
            keep_case=True))
        if response.body:
            self.send(h11.Data(data=response.body))
        self.send(h11.EndOfMessage())

    def send_info_response(self, response):
        self.send(h11.InformationalResponse(
            status_code=response.code,
            headers=response.headers.get_list(),
            keep_case=True))
