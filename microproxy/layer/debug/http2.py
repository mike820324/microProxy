from tornado import concurrent

from h2.connection import H2Connection
from h2.exceptions import NoSuchStreamError
from h2.events import RequestReceived, WindowUpdated

from microproxy.utils import get_logger
logger = get_logger(__name__)


class Http2Layer(object):
    def __init__(self, context):
        super(Http2Layer, self).__init__()
        self.context = context
        self.src_conn = Connection(
            self.context.src_stream, self.context.dest_stream, False,
            self, client_side=False)
        self.dest_conn = Connection(
            self.context.dest_stream, self.context.src_stream, True,
            self, client_side=True)
        self._future = concurrent.Future()

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
            self._future.set_result(self.context)

    def on_dest_close(self):
        self.context.src_stream.close()
        if self._future.running():
            self._future.set_result(self.context)

    def on_request_header(self, stream_id, headers):
        self.dest_conn.send_headers(stream_id, headers)

    def on_window_update(self, src_conn, event):
        if src_conn is self.src_conn:
            self.dest_conn.increment_flow_control_window(
                event.delta, event.stream_id or None)
        else:
            self.src_conn.increment_flow_control_window(
                event.delta, event.stream_id or None)


class Connection(H2Connection):
    def __init__(self, from_stream, to_stream, is_server, layer, *args, **kwargs):
        super(Connection, self).__init__(*args, **kwargs)
        self.from_stream = from_stream
        self.to_stream = to_stream
        self._type = "dest" if is_server else "src"
        self.layer = layer

    def on_data_received(self, data):
        try:
            self.to_stream.write(data)
            events = self.receive_data(data)
            for event in events:
                logger.debug("event received from {0}: {1}".format(
                    self._type, event))
                if isinstance(event, RequestReceived):
                    self.layer.on_request_header(event.stream_id, event.headers)
                elif isinstance(event, WindowUpdated):
                    self.layer.on_window_update(self, event)
        except NoSuchStreamError as e:
            logger.error("NoSuchStreamError with stream_id: {0} on {1}".format(e.stream_id, self._type))
            logger.exception(e)
        except Exception as e:
            logger.error("Exception on {0}".format(self._type))
            logger.exception(e)
