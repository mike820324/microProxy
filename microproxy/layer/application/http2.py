from tornado import concurrent, gen
from h2.connection import H2Connection
from h2.events import (
    ResponseReceived, RequestReceived, DataReceived, StreamEnded,
    StreamReset, RemoteSettingsChanged
)

from microproxy.interceptor import signal_publish
from microproxy.utils import get_logger
from microproxy import http
logger = get_logger(__name__)


class Http2Layer(object):
    '''
    ForwardLayer: passing all the src data to destination. Will not intercept anything
    '''
    def __init__(self, context):
        super(Http2Layer, self).__init__()
        self.context = context
        self.src_conn = Connection(self, self.context.src_stream, client_side=False)
        self.dest_conn = Connection(self, self.context.dest_stream, client_side=True)
        self.result = dict()
        self._future = concurrent.Future()

    @gen.coroutine
    def process_and_return_context(self):
        yield self._init_h2_connection()
        self.context.src_stream.read_until_close(streaming_callback=self.src_conn.on_data_received)
        self.context.src_stream.set_close_callback(self.on_src_close)
        self.context.dest_stream.read_until_close(streaming_callback=self.dest_conn.on_data_received)
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

    def on_request_header(self, src_stream_id, headers):
        headers_dict = dict(headers)
        headers.append(("Host", self.context.host))
        self.result[src_stream_id] = dict(
            request=http.HttpRequest(
                version="HTTP/2",
                method=headers_dict[":method"],
                path=headers_dict[":path"],
                headers=headers))

    def on_response_header(self, src_stream_id, headers):
        headers_dict = dict(headers)
        self.result[src_stream_id]["response"] = http.HttpResponse(
            version="HTTP/2",
            code=headers_dict[":status"],
            headers=headers)
        signal_publish.send(
            self,
            request=self.result[src_stream_id]["request"],
            response=self.result[src_stream_id]["response"])


class Connection(H2Connection):
    def __init__(self, http2_layer, stream, *args, **kwargs):
        super(Connection, self).__init__(*args, **kwargs)
        self.http2_layer = http2_layer
        self.stream = stream
        self._type = "dest" if kwargs["client_side"] else "src"
        self.to_stream_ids = dict([(0, 0)])

    def flush(self):
        data = self.data_to_send()
        logger.debug("data send to {0} with length:  {1}".format(self._type, len(data)))
        return self.stream.write(data)

    def on_data_received(self, data):
        try:
            logger.debug("data received from {0} with length {1}".format(self._type, len(data)))
            events = self.receive_data(data)
            self.flush()
            self.handle_events(events)
        except Exception as e:
            logger.exception(e)

    def handle_events(self, events):
        for event in events:
            logger.debug("event received from {0}: {1}".format(self._type, event))
            if isinstance(event, ResponseReceived):
                self.handle_response(event.headers, event.stream_id)
            elif isinstance(event, RequestReceived):
                self.handle_request(event.headers, event.stream_id)
            elif isinstance(event, DataReceived):
                self.handle_data(event.data, event.stream_id)
            elif isinstance(event, StreamEnded):
                self.handle_end_stream(event.stream_id)
            elif isinstance(event, StreamReset):
                logger.error("Stream reset: {0}".format(event.error_code))
            elif isinstance(event, RemoteSettingsChanged):
                self.handle_update_settings(event)
            else:
                logger.warn("not handled event: {0}".format(event))

    def handle_request(self, headers, stream_id):
        write_conn = self.http2_layer.get_target_conn(self)

        server_stream_id = write_conn.get_next_available_stream_id()
        self.to_stream_ids[stream_id] = server_stream_id
        write_conn.to_stream_ids[server_stream_id] = stream_id

        logger.debug("source to destination with stream id {0}->{1}".format(stream_id, server_stream_id))

        write_conn.send_headers(server_stream_id, headers)
        write_conn.flush()

        self.http2_layer.on_request_header(stream_id, headers)

    def handle_response(self, headers, stream_id):
        write_conn = self.http2_layer.get_target_conn(self)
        client_stream_id = self.to_stream_ids[stream_id]

        logger.debug("destination to source with stream id {0}->{1}".format(stream_id, client_stream_id))
        write_conn.send_headers(client_stream_id, headers)
        write_conn.flush()

        self.http2_layer.on_response_header(client_stream_id, headers)

    def handle_data(self, data, stream_id):
        write_conn = self.http2_layer.get_target_conn(self)
        write_conn.send_data(self.to_stream_ids[stream_id], data)
        write_conn.flush()

    def handle_update_settings(self, event):
        write_conn = self.http2_layer.get_target_conn(self)
        new_settings = dict([(id, cs.new_value) for (id, cs) in event.changed_settings.iteritems()])
        write_conn.update_settings(new_settings)
        write_conn.flush()

    def handle_end_stream(self, stream_id):
        write_conn = self.http2_layer.get_target_conn(self)
        write_conn.end_stream(self.to_stream_ids[stream_id])
        write_conn.flush()
