from tornado import concurrent, gen
from h2.connection import H2Connection
from h2.events import (
    ResponseReceived, RequestReceived, DataReceived, StreamEnded,
    StreamReset, RemoteSettingsChanged, WindowUpdated,
    PushedStreamReceived, PriorityUpdated
)
from h2.exceptions import ProtocolError, NoSuchStreamError

from microproxy.context import HttpRequest, HttpResponse
from microproxy.interceptor import signal_request, signal_response, signal_publish
from microproxy.utils import get_logger

logger = get_logger(__name__)


class Http2Layer(object):
    '''
    Http2Layer: Responsible for handling the http2 request and response.
    '''
    def __init__(self, context):
        super(Http2Layer, self).__init__()
        self.context = context
        self.src_conn = Connection(
            self, self.context.src_stream, client_side=False)
        self.dest_conn = Connection(
            self, self.context.dest_stream, client_side=True)
        self.streams = dict()
        self._future = concurrent.Future()

    @gen.coroutine
    def process_and_return_context(self):
        yield self._init_h2_connection()
        self.context.src_stream.read_until_close(
            streaming_callback=self.src_conn.on_data_received)
        self.context.src_stream.set_close_callback(self.on_src_close)

        self.context.dest_stream.read_until_close(
            streaming_callback=self.dest_conn.on_data_received)
        self.context.dest_stream.set_close_callback(self.on_dest_close)
        result = yield self._future
        raise gen.Return(result)

    @gen.coroutine
    def _init_h2_connection(self):
        self.dest_conn.initiate_connection()
        yield self.dest_conn.flush()
        self.src_conn.initiate_connection()
        yield self.src_conn.flush()

    def on_src_close(self):
        logger.debug("src stream closed")
        self.context.dest_stream.close()
        if self._future.running():
            self._future.set_result(self.context)

    def on_dest_close(self):
        logger.debug("dest stream closed")
        self.context.src_stream.close()
        if self._future.running():
            self._future.set_result(self.context)

    def get_target_conn(self, from_conn):
        return self.dest_conn if from_conn is self.src_conn else self.src_conn

    def on_request_header(self, src_stream_id, headers, priority_updated):
        stream = Stream()
        stream.write_request_headers(headers)
        self.priority_updated = priority_updated
        self.streams[src_stream_id] = stream

    def on_request_body(self, src_stream_id, data):
        self.streams[src_stream_id].write_request_body(data)

    def get_request(self, src_stream_id):
        stream = self.streams[src_stream_id]
        stream.request_done()

        plugin_response = signal_request.send(
            self, layer_context=self.context, request=stream.req)

        new_req = plugin_response[0][1].request if len(plugin_response) else stream.req
        stream.req = new_req
        return (new_req.headers.get_list(), new_req.body, stream.priority_updated)

    def on_response_header(self, src_stream_id, headers):
        self.streams[src_stream_id].write_response_headers(headers)

    def on_pushed_header(self, src_stream_id, headers):
        self.on_request_header(src_stream_id, headers, None)
        stream = self.streams[src_stream_id]
        stream.request_done()

    def on_response_body(self, src_stream_id, data):
        self.streams[src_stream_id].write_response_body(data)

    def get_response(self, src_stream_id):
        stream = self.streams[src_stream_id]
        stream.response_done()

        plugin_response = signal_response.send(
            self, layer_context=self.context,
            request=stream.req, response=stream.resp)

        new_resp = plugin_response[0][1].response if len(plugin_response) else stream.resp
        stream.resp = new_resp
        return (new_resp.headers.get_list(), new_resp.body)

    def on_finish(self, src_stream_id):
        stream = self.streams[src_stream_id]

        signal_publish.send(
            self, layer_context=self.context,
            request=stream.req, response=stream.resp)


class Connection(H2Connection):
    def __init__(self, http2_layer, stream, *args, **kwargs):
        super(Connection, self).__init__(*args, **kwargs)
        self.http2_layer = http2_layer
        self.stream = stream
        self.to_stream_ids = dict([(0, 0)])
        self._type = "dest" if kwargs["client_side"] else "src"

    def flush(self):
        data = self.data_to_send()
        return self.stream.write(data)

    def on_data_received(self, data):
        try:
            logger.debug("data received from {0} with length {1}".format(self._type, len(data)))
            events = self.receive_data(data)
            self.flush()
            self.handle_events(events)
        except Exception as e:
            logger.exception(e)
            self.stream.closed()

    def handle_events(self, events):
        for event in events:
            logger.debug("event received from {0}: {1}".format(self._type, event))
            if isinstance(event, ResponseReceived):
                self.handle_response(event.headers, event.stream_id)
            elif isinstance(event, RequestReceived):
                self.handle_request(event)
            elif isinstance(event, DataReceived):
                self.handle_data(event.data, event.stream_id, event.flow_controlled_length)
            elif isinstance(event, StreamEnded):
                self.handle_end_stream(event.stream_id)
            elif isinstance(event, StreamReset):
                self.handle_reset(event.stream_id, event.error_code)
            elif isinstance(event, RemoteSettingsChanged):
                self.handle_update_settings(event)
            elif isinstance(event, WindowUpdated):
                self.handle_window_updates(event)
            elif isinstance(event, PushedStreamReceived):
                self.handle_pushed_stream(event)
            elif isinstance(event, PriorityUpdated):
                self.handle_priority_updates(event)
            else:
                logger.debug("not handled event: {0}".format(event))

    def handle_request(self, event):
        self.http2_layer.on_request_header(
            event.stream_id, event.headers, event.priority_updated)

    def handle_response(self, headers, stream_id):
        self.http2_layer.on_response_header(self.to_stream_ids[stream_id], headers)

    def handle_data(self, data, stream_id, flow_controlled_length):
        if self._is_source_conn():
            self.http2_layer.on_request_body(stream_id, data)
        else:
            self.http2_layer.on_response_body(self.to_stream_ids[stream_id], data)

        if flow_controlled_length > 0:
            self.increment_flow_control_window(flow_controlled_length)
            self.flush()

    def handle_update_settings(self, event):
        write_conn = self.http2_layer.get_target_conn(self)
        new_settings = {id: cs.new_value for (id, cs) in event.changed_settings.iteritems()}
        write_conn.update_settings(new_settings)
        write_conn.flush()
        logger.debug("settings update sent to {0}: {1}".format(
            write_conn._type,
            new_settings)
        )

    def handle_end_stream(self, stream_id):
        write_conn = self.http2_layer.get_target_conn(self)
        if self._is_source_conn():
            dest_stream_id = write_conn.get_next_available_stream_id()
            self.to_stream_ids[stream_id] = dest_stream_id
            write_conn.to_stream_ids[dest_stream_id] = stream_id

            headers, body, priority_updated = self.http2_layer.get_request(stream_id)
            has_body = len(body) > 0
            write_conn.write_headers(
                dest_stream_id, headers, stream_ended=not has_body,
                priority_weight=priority_updated.priority_weight if priority_updated else None,
                priority_exclusive=priority_updated.priority_exclusive if priority_updated else None,
                priority_depends_on=self.safe_map_to_stream_id(priority_updated.depends_on) if priority_updated else None
            )
            if has_body:
                write_conn.write_data(dest_stream_id, body)
            logger.debug("request {0}->{1}".format(stream_id, dest_stream_id))
        else:
            src_stream_id = self.to_stream_ids[stream_id]

            headers, body = self.http2_layer.get_response(src_stream_id)
            write_conn.write_headers(
                src_stream_id, headers, stream_ended=False)
            write_conn.write_data(src_stream_id, body, stream_ended=True)

            self.http2_layer.on_finish(src_stream_id)
            logger.debug("response {0}->{1}".format(stream_id, src_stream_id))

    def safe_map_to_stream_id(self, stream_id):
        if stream_id in self.to_stream_ids.keys():
            return self.to_stream_ids[stream_id]
        return None

    def handle_window_updates(self, event):
        to_stream_id = self.safe_map_to_stream_id(event.stream_id) or None
        write_conn = self.http2_layer.get_target_conn(self)
        write_conn.increment_flow_control_window(event.delta, to_stream_id)
        write_conn.flush()
        logger.debug("window update sent to {0}: {1}".format(
            write_conn._type,
            dict(delta=event.delta,
                 stream_id=to_stream_id))
        )

    def handle_pushed_stream(self, event):
        write_conn = self.http2_layer.get_target_conn(self)

        self.to_stream_ids[event.pushed_stream_id] = event.pushed_stream_id
        write_conn.to_stream_ids[event.pushed_stream_id] = event.pushed_stream_id

        to_parent_stream_id = self.to_stream_ids[event.parent_stream_id]

        self.http2_layer.on_pushed_header(event.pushed_stream_id, event.headers)
        write_conn.push_stream(
            to_parent_stream_id,
            event.pushed_stream_id,
            event.headers)
        write_conn.flush()

        logger.debug("push {0} with parent {1}->{2}".format(
            event.pushed_stream_id, event.parent_stream_id, to_parent_stream_id))

    def handle_priority_updates(self, event):
        write_conn = self.http2_layer.get_target_conn(self)
        to_stream_id = self.safe_map_to_stream_id(event.stream_id)
        to_depends_on_id = self.safe_map_to_stream_id(event.depends_on)

        if to_stream_id and to_depends_on_id:
            logger.debug("priority updated sent: {0}".format(
                dict(stream_id=to_stream_id,
                     priority_weight=event.weight,
                     priority_depends_on=to_depends_on_id,
                     priority_exclusive=event.exclusive))
            )
            write_conn.prioritize(
                to_stream_id, event.weight,
                to_depends_on_id, event.exclusive)
            write_conn.flush()

    def write_headers(self, stream_id, headers, stream_ended=False, **kwargs):
        try:
            self.send_headers(stream_id, headers, end_stream=stream_ended, **kwargs)
            self.flush()
        except ProtocolError:
            logger.error("write headers failed on stream id: {0}".format(stream_id))

    def write_data(self, stream_id, body, stream_ended=True):
        try:
            chunks = [body] if isinstance(body, str) else body
            position = 0
            for chunk in chunks:
                while position < len(chunk):
                    max_outbound_frame_size = self.max_outbound_frame_size
                    frame_chunk = chunk[position:position + max_outbound_frame_size]
                    self.send_data(stream_id, frame_chunk)
                    self.flush()
                    position += max_outbound_frame_size
            if stream_ended:
                self.end_stream(stream_id)
                self.flush()
        except NoSuchStreamError as e:
            logger.error("stream id not found on {0} with {1}".format(
                self._type, stream_id))
            logger.exception(e)

    def handle_reset(self, stream_id, error_code):
        if error_code == 0x8:
            write_conn = self.http2_layer.get_target_conn(self)
            write_conn.reset_stream(self.to_stream_ids[stream_id], error_code)
            logger.debug("reset {0}({1})->{2}({3}) with {4}".format(
                self._type, stream_id, write_conn._type, self.to_stream_ids[stream_id], error_code))

    def _is_source_conn(self):
        return self._type == "src"


class Stream(object):
    def __init__(self):
        super(Stream, self).__init__()
        self.req = None
        self.resp = None
        self.req_headers = None
        self.req_chunks = []
        self.priority_updated = None
        self.resp_headers = None
        self.resp_chunks = []

    def write_request_headers(self, headers):
        self.req_headers = headers

    def write_request_body(self, data):
        self.req_chunks.append(data)

    def request_done(self):
        headers_dict = dict(self.req_headers)
        self.req = HttpRequest(
            version="HTTP/2",
            method=headers_dict[":method"],
            path=headers_dict[":path"],
            headers=self.req_headers,
            body=b"".join(self.req_chunks))

    def write_response_headers(self, headers):
        self.resp_headers = headers

    def write_response_body(self, data):
        self.resp_chunks.append(data)

    def response_done(self):
        headers_dict = dict(self.resp_headers)
        self.resp = HttpResponse(
            version="HTTP/2",
            code=headers_dict[":status"],
            headers=self.resp_headers,
            body=b"".join(self.resp_chunks))
