from h2.connection import H2Connection
from h2.events import (
    ResponseReceived, RequestReceived, DataReceived, StreamEnded,
    StreamReset, RemoteSettingsChanged, WindowUpdated,
    PushedStreamReceived, PriorityUpdated,
    SettingsAcknowledged, ConnectionTerminated
)
from h2.exceptions import ProtocolError, NoSuchStreamError

from tornado import concurrent

from microproxy.context import HttpRequest, HttpResponse
from microproxy.utils import get_logger

logger = get_logger(__name__)


class Connection(H2Connection):
    _DEFAULT_TYPES = dict([
        (True, "client"),
        (False, "server")])
    _VERSION = "HTTP/2"

    def __init__(self, stream, client_side=False, conn_type=None,
                 on_request=None, on_response=None, on_push=None,
                 on_settings=None, on_window_updates=None,
                 on_priority_updates=None, on_reset=None,
                 on_terminate=None, readonly=False, **kwargs):
        super(Connection, self).__init__(client_side=client_side, **kwargs)
        self.stream = stream
        self.on_request = on_request
        self.on_response = on_response
        self.on_push = on_push
        self.on_settings = on_settings
        self.on_priority_updates = on_priority_updates
        self.on_reset = on_reset
        self.on_window_updates = on_window_updates
        self.on_terminate = on_terminate
        self.conn_type = conn_type or self._DEFAULT_TYPES[client_side]
        self.readonly = readonly
        self.ongoings_streams = dict()

    def flush(self):
        if not self.readonly:
            data = self.data_to_send()
            if data:
                return self.stream.write(data)
        else:
            future = concurrent.Future()
            future.set_result(None)
            return future

    def receive(self, data):
        try:
            logger.debug("data received from {0} with length {1}".format(self.conn_type, len(data)))
            events = self.receive_data(data)
            self.handle_events(events)
        except Exception as e:
            logger.error("Unhandled exception occured at {0}".format(self.conn_type))
            logger.exception(e)
            self.stream.closed()

    def handle_events(self, events):
        for event in events:
            logger.debug("event received from {0}: {1}".format(self.conn_type, event))
            if isinstance(event, ResponseReceived):
                self.handle_response(event)
            elif isinstance(event, RequestReceived):
                self.handle_request(event)
            elif isinstance(event, DataReceived):
                self.handle_data(event)
            elif isinstance(event, StreamEnded):
                self.handle_end_stream(event.stream_id)
            elif isinstance(event, StreamReset):
                self.handle_reset(event)
            elif isinstance(event, RemoteSettingsChanged):
                self.handle_update_settings(event)
            elif isinstance(event, WindowUpdated):
                self.handle_window_updates(event)
            elif isinstance(event, PushedStreamReceived):
                self.handle_pushed_stream(event)
            elif isinstance(event, PriorityUpdated):
                self.handle_priority_updates(event)
            elif isinstance(event, ConnectionTerminated):
                self.on_terminate()
            elif isinstance(event, SettingsAcknowledged):
                # Note: nothing need to do with this event
                pass
            else:
                logger.warn("not handled event: {0}".format(event))

    def handle_request(self, event):
        headers_dict = dict(event.headers)
        self.ongoings_streams[event.stream_id] = (
            HttpRequest(
                version=self._VERSION,
                method=headers_dict[":method"],
                path=headers_dict[":path"],
                headers=event.headers), [], event.priority_updated)

    def handle_response(self, event):
        headers_dict = dict(event.headers)
        self.ongoings_streams[event.stream_id] = (
            HttpResponse(
                version=self._VERSION,
                code=headers_dict[":status"],
                headers=event.headers), [], None)

    def handle_data(self, event):
        _, chunks, _ = self.ongoings_streams[event.stream_id]
        chunks.append(event.data)

        if event.flow_controlled_length > 0:
            self.increment_flow_control_window(event.flow_controlled_length)
            self.flush()

    def handle_end_stream(self, stream_id):
        if self.client_side:
            response, chunks, _ = self.ongoings_streams[stream_id]
            response.body = b"".join(chunks)
            self.on_response(stream_id, response)
        else:
            request, chunks, priority_updated = self.ongoings_streams[stream_id]
            request.body = b"".join(chunks)
            self.on_request(stream_id, request, priority_updated)

    def handle_pushed_stream(self, event):
        headers_dict = dict(event.headers)
        request = HttpRequest(
            version=self._VERSION,
            method=headers_dict[":method"],
            path=headers_dict[":path"],
            headers=event.headers)

        self.on_push(event.pushed_stream_id,
                     event.parent_stream_id,
                     request)

    def handle_update_settings(self, event):
        self.on_settings(event.changed_settings)

    def handle_window_updates(self, event):
        self.on_window_updates(event.stream_id, event.delta)

    def handle_priority_updates(self, event):
        self.on_priority_updates(
            event.stream_id, event.depends_on, event.weight, event.exclusive)

    def handle_reset(self, event):
        self.on_reset(event.stream_id, event.error_code)

    def send_request(self, stream_id, request, **kwargs):
        logger.debug("request sent to {0}: {1}".format(
            self.conn_type, dict(stream_id=stream_id, request=dict(
                headers=request.headers))))
        self.send_headers(
            stream_id, request.headers, stream_ended=not bool(request.body), **kwargs)
        if request.body:
            self.send_data(stream_id, request.body)

    def send_response(self, stream_id, response):
        logger.debug("response sent to {0}: {1}".format(
            self.conn_type, dict(stream_id=stream_id, response=dict(
                headers=response.headers))))
        self.send_headers(
            stream_id, response.headers,
            stream_ended=not bool(response.body))
        if response.body:
            self.send_data(stream_id, response.body)

    def _send_headers(self, *args, **kwargs):
        super(Connection, self).send_headers(*args, **kwargs)

    def send_headers(self, stream_id, headers, stream_ended=False, **kwargs):
        try:
            self._send_headers(stream_id, headers, end_stream=stream_ended, **kwargs)
            self.flush()
        except ProtocolError:
            logger.error("send headers failed on stream id: {0}".format(stream_id))

    def _send_data(self, *args, **kwargs):
        super(Connection, self).send_data(*args, **kwargs)

    def send_data(self, stream_id, body, stream_ended=True):
        try:
            chunks = [body] if isinstance(body, str) else body
            position = 0
            for chunk in chunks:
                while position < len(chunk):
                    max_outbound_frame_size = self.max_outbound_frame_size
                    frame_chunk = chunk[position:position + max_outbound_frame_size]
                    self._send_data(stream_id, frame_chunk)
                    self.flush()
                    position += max_outbound_frame_size
            if stream_ended:
                self.end_stream(stream_id)
                self.flush()
        except NoSuchStreamError as e:
            logger.error("stream id not found on {0} with {1}".format(
                self.conn_type, stream_id))
            logger.exception(e)

    def send_update_settings(self, new_settings):
        logger.debug("settings update sent to {0}: {1}".format(
            self.conn_type, new_settings))
        self.update_settings(new_settings)
        self.flush()

    def send_window_updates(self, stream_id, delta):
        stream_id = stream_id or None
        logger.debug("window updates sent to {0}: {1}".format(
            self.conn_type, locals()))
        self.increment_flow_control_window(delta, stream_id)
        self.flush()

    def send_priority_updates(self, stream_id, depends_on, weight, exclusive):
        logger.debug("priority updated sent to {0}: {1}".format(
            self.conn_type, locals()))
        self.prioritize(
            stream_id, weight,
            depends_on, exclusive)
        self.flush()

    def send_pushed_stream(self, stream_id, promised_stream_id, request):
        logger.debug("pushed sent to {0}: {1}".format(
            self.conn_type, locals()))
        self.push_stream(
            stream_id,
            promised_stream_id,
            request.headers)
        self.flush()

    def send_reset(self, stream_id, error_code):
        logger.debug("reset sent to {0}: {1}".format(
            self.conn_type, locals()))
        self.reset_stream(stream_id, error_code)
        self.flush()

    def send_terminate(self):
        self.close_connection()
        self.flush()
