from tornado import concurrent

import h11
from h11 import Connection as H11Connection
from h11 import Request, InformationalResponse, Response, Data, EndOfMessage

from microproxy.exception import SrcStreamClosedError, DestStreamClosedError
from microproxy.context import HttpRequest, HttpResponse
from microproxy.utils import get_logger
logger = get_logger(__name__)


class Http1Layer(object):
    def __init__(self, context):
        super(Http1Layer, self).__init__()
        self.context = context
        self.src_conn = Connection(
            self.context.src_stream, False, self, our_role=h11.SERVER)
        self.dest_conn = Connection(
            self.context.dest_stream, True, self, our_role=h11.CLIENT)
        self._future = concurrent.Future()
        self.http_stream = None

    def process_and_return_context(self):
        self.context.src_stream.read_until_close(
            streaming_callback=self.src_conn.on_data_received)
        self.context.src_stream.set_close_callback(self.on_src_close)

        self.context.dest_stream.read_until_close(
            streaming_callback=self.dest_conn.on_data_received)
        self.context.dest_stream.set_close_callback(self.on_dest_close)
        return self._future

    def on_src_close(self):
        self.context.dest_stream.close()
        if self._future.running():
            if self.http_stream:  # contains running request
                self._future.set_exception(SrcStreamClosedError())
            else:
                self._future.set_result(self.context)

    def on_dest_close(self):
        self.context.src_stream.close()
        if self._future.running():
            if self.http_stream:  # contains running request
                self._future.set_exception(DestStreamClosedError())
            else:
                self._future.set_result(self.context)

    def get_target_conn(self, from_conn):
        return self.dest_conn if from_conn is self.src_conn else self.src_conn

    def on_request_header(self, header):
        stream = Stream()
        stream.write_request_header(header)
        self.http_stream = stream

    def on_request_body(self, data):
        self.http_stream.write_request_body(data)

    def get_request(self):
        self.http_stream.request_done(self.context)
        return self.http_stream.req

    def on_response_header(self, header):
        self.http_stream.write_response_header(header)

    def on_response_body(self, data):
        self.http_stream.write_response_body(data)

    def get_response(self):
        self.http_stream.response_done(self.context)
        return self.http_stream.resp

    def on_finish(self):
        self.context.interceptor.publish(
            layer_context=self.context,
            request=self.http_stream.req,
            response=self.http_stream.resp
        )

        self.http_stream = None
        self.src_conn.start_next_cycle()
        self.dest_conn.start_next_cycle()


class Connection(H11Connection):
    def __init__(self, io_stream, is_server, layer, *args, **kwargs):
        super(Connection, self).__init__(*args, **kwargs)
        self.io_stream = io_stream
        self._type = "dest" if is_server else "src"
        self.layer = layer

    def write(self, event):
        logger.debug("event send to {0}: {1}".format(self._type, type(event)))
        data = self.send(event)
        self.io_stream.write(data)

    def on_data_received(self, data):
        try:
            logger.debug("data received from {0} with length {1}".format(self._type, len(data)))
            self.receive_data(data)
            while True:
                event = self.next_event()
                if isinstance(event, Request):
                    logger.debug("event recevied from {0}: {1}".format(self._type, repr(event)))
                    self.layer.on_request_header(event)
                elif isinstance(event, InformationalResponse):
                    logger.debug("event recevied from {0}: {1}".format(self._type, repr(event)))
                    pass
                elif isinstance(event, Response):
                    self.layer.on_response_header(event)
                elif isinstance(event, Data):
                    logger.debug("event recevied from {0}: {1}".format(self._type, type(event)))
                    if self._is_source_conn():
                        self.layer.on_request_body(event)
                    else:
                        self.layer.on_response_body(event)
                elif isinstance(event, EndOfMessage):
                    logger.debug("event recevied from {0}: {1}".format(self._type, repr(event)))
                    if self._is_source_conn():
                        request = self.layer.get_request()
                        self.send_request(request)
                    else:
                        response = self.layer.get_response()
                        self.send_response(response)
                        self.layer.on_finish()
                elif event is h11.NEED_DATA:
                    logger.debug("event recevied from {0}: {1}".format(self._type, repr(event)))
                    break
                elif event is h11.PAUSED:
                    logger.debug("event recevied from {0}: {1}".format(self._type, repr(event)))
                    break
                else:
                    logger.debug("event recevied was not handled from {0}: {1}".format(self._type, repr(event)))
        except Exception as e:
            logger.error("Exception on {0}".format(self._type))
            logger.exception(e)

    def send_request(self, request):
        target_conn = self.layer.get_target_conn(self)
        target_conn.write(h11.Request(
            method=request.method,
            target=request.path,
            headers=request.headers.get_list()))
        if request.body:
            target_conn.write(h11.Data(data=request.body))
        target_conn.write(h11.EndOfMessage())

    def send_response(self, response):
        target_conn = self.layer.get_target_conn(self)
        target_conn.write(h11.Response(
            status_code=response.code,
            headers=response.headers.get_list()))
        if response.body:
            target_conn.write(h11.Data(data=response.body))
        target_conn.write(h11.EndOfMessage())

    def _is_source_conn(self):
        return self._type == "src"


class Stream(object):
    def __init__(self):
        super(Stream, self).__init__()
        self.req = None
        self.resp = None
        self.req_header = None
        self.req_chunks = []
        self.resp_header = None
        self.resp_chunks = []

    def write_request_header(self, header):
        self.req_header = header

    def write_request_body(self, data):
        self.req_chunks.append(bytes(data.data))

    def request_done(self, layer_context):
        try:
            version = "HTTP/{0}".format(self.req_header.http_version)
        except:
            version = "HTTP/1.1"
        req = HttpRequest(
            version=version,
            method=self.req_header.method,
            path=self.req_header.target,
            headers=self.req_header.headers,
            body=b"".join(self.req_chunks))

        plugin_resp = layer_context.interceptor.request(
            layer_context=layer_context, request=req
        )
        self.req = plugin_resp.request if plugin_resp else req

    def write_response_header(self, header):
        self.resp_header = header

    def write_response_body(self, data):
        self.resp_chunks.append(bytes(data.data))

    def response_done(self, layer_context):
        try:
            version = "HTTP/{0}".format(self.req_header.http_version)
        except:
            version = "HTTP/1.1"
        resp = HttpResponse(
            version=version,
            reason=self.resp_header.reason,
            code=self.resp_header.status_code,
            headers=self.resp_header.headers,
            body=b"".join(self.resp_chunks))

        plugin_resp = layer_context.interceptor.response(
            layer_context=layer_context, request=self.req, response=resp
        )

        self.resp = plugin_resp.response if plugin_resp else resp
