from tornado import concurrent, gen

from h2.events import (
    StreamReset, WindowUpdated, PriorityUpdated,
)

from microproxy.layer.base import ApplicationLayer
from microproxy.protocol.http2 import Connection

from microproxy.log import ProxyLogger
logger = ProxyLogger.get_logger(__name__)


class Http2Layer(ApplicationLayer):
    '''
    Http2Layer: Responsible for handling the http2 request and response.
    '''
    def __init__(self, server_state, context):
        super(Http2Layer, self).__init__(server_state, context)
        self.src_conn = Connection(
            self.src_stream, client_side=False,
            conn_type="source",
            on_header_receive=self.on_src_header_receive,
            on_request=self.on_request,
            on_settings=self.on_src_settings,
            on_window_updates=self.on_src_window_updates,
            on_priority_updates=self.on_src_priority_updates,
            on_reset=self.on_src_reset,
            on_terminate=self.on_src_terminate,
            readonly=(context.mode == "replay"))

        self.dest_conn = Connection(
            self.dest_stream, client_side=True,
            conn_type="destination",
            on_response=self.on_response,
            on_pending_events=self.on_dest_pending_events,
            on_push=self.on_push,
            on_settings=self.on_dest_settings,
            on_window_updates=self.on_dest_window_updates,
            on_terminate=self.on_dest_terminate,
            on_reset=self.on_dest_reset)
        self.streams = dict()
        self.pending_events_of_stream = dict()
        self.should_pending_streams = set()
        self._future = concurrent.Future()

    @gen.coroutine
    def process_and_return_context(self):
        yield self._init_h2_connection()
        self.src_stream.read_until_close(
            streaming_callback=self.src_conn.receive)
        self.src_stream.set_close_callback(self.on_src_close)

        self.dest_stream.read_until_close(
            streaming_callback=self.dest_conn.receive)
        self.dest_stream.set_close_callback(self.on_dest_close)
        result = yield self._future
        raise gen.Return(result)

    @gen.coroutine
    def _init_h2_connection(self):
        self.dest_conn.initiate_connection()
        yield self.dest_conn.flush()
        self.src_conn.initiate_connection()
        yield self.src_conn.flush()

    def on_src_close(self):
        logger.debug("{0}: src stream closed".format(self))
        self.dest_stream.close()
        self.layer_finish()

    def on_dest_close(self):
        logger.debug("{0}: dest stream closed".format(self))
        self.src_stream.close()
        self.layer_finish()

    def layer_finish(self):
        if self._future.running():
            self._future.set_result(self.context)

    def on_dest_pending_events(self, stream_id):
        # NOTE: When we reach to this point, we can be sure that the header is being sent,
        # Remove the stread id from shadow idle stream.
        self.should_pending_streams.remove(stream_id)
        pending_events = self.pending_events_of_stream.pop(stream_id, [])

        # NOTE: Since our header frame is being sent,
        # if we have any pending events, pop it to the peers.
        for event in pending_events:
            if isinstance(event, WindowUpdated):
                self.on_src_window_updates(event.stream_id, event.delta)
            elif isinstance(event, PriorityUpdated):
                self.on_src_priority_updates(
                    event.stream_id, event.depends_on, event.weight, event.exclusive)
            elif isinstance(event, StreamReset):
                self.on_src_reset(event.stream_id, event.error_code)

    def on_src_header_receive(self, stream_id):
        self.should_pending_streams.add(stream_id)

    def on_request(self, stream_id, request, priority_updated):
        if priority_updated:
            priority_weight = priority_updated.weight
            priority_exclusive = priority_updated.exclusive
            priority_depends_on = priority_updated.depends_on
        else:
            priority_weight = None
            priority_exclusive = None
            priority_depends_on = None

        stream = Stream(self, self.context, stream_id)
        stream.on_request(
            request,
            priority_weight=priority_weight,
            priority_exclusive=priority_exclusive,
            priority_depends_on=priority_depends_on)
        self.streams[stream_id] = stream

    def on_push(self, pushed_stream_id, parent_stream_id, request):
        stream = Stream(self, self.context, pushed_stream_id)
        stream.on_push(request, parent_stream_id)
        self.streams[pushed_stream_id] = stream

    def on_response(self, stream_id, response):
        self.streams[stream_id].on_response(response)

        self.on_finish(stream_id)

    def on_finish(self, src_stream_id):
        stream = self.streams[src_stream_id]

        self.interceptor.publish(
            layer_context=self.context, request=stream.request,
            response=stream.response)
        del self.streams[src_stream_id]

        if self.context.mode == "replay":
            self.src_stream.close()
            self.dest_stream.close()

    def on_src_settings(self, changed_settings):
        new_settings = {
            id: cs.new_value for (id, cs) in changed_settings.iteritems()
        }
        self.dest_conn.send_update_settings(new_settings)

    def on_dest_settings(self, changed_settings):
        new_settings = {
            id: cs.new_value for (id, cs) in changed_settings.iteritems()
        }
        self.src_conn.send_update_settings(new_settings)

    def on_src_window_updates(self, stream_id, delta, event=None):
        if stream_id in self.should_pending_streams:
            try:
                self.pending_events_of_stream[stream_id].append(event)
            except KeyError:
                self.pending_events_of_stream[stream_id] = []

        else:
            self.dest_conn.send_window_updates(stream_id, delta)

    def on_dest_window_updates(self, stream_id, delta, event=None):
        target_stream_id = stream_id
        self.src_conn.send_window_updates(target_stream_id, delta)

    def on_src_priority_updates(self, stream_id, depends_on,
                                weight, exclusive, event=None):
        if stream_id in self.should_pending_streams:
            try:
                self.pending_events_of_stream[stream_id].append(event)
            except KeyError:
                self.pending_events_of_stream[stream_id] = []

        else:
            self.dest_conn.send_priority_updates(
                stream_id, depends_on, weight, exclusive)

    def on_src_reset(self, stream_id, error_code, event=None):
        if stream_id in self.should_pending_streams:
            try:
                self.pending_events_of_stream[stream_id].append(event)
            except KeyError:
                self.pending_events_of_stream[stream_id] = []

        else:
            self.dest_conn.send_reset(stream_id, error_code)

    def on_dest_reset(self, stream_id, error_code, event=None):
        self.src_conn.send_reset(stream_id, error_code)

    def on_src_terminate(self, additional_data, error_code, last_stream_id):
        self.dest_conn.send_terminate(
            error_code=error_code,
            additional_data=additional_data,
            last_stream_id=last_stream_id)

    def on_dest_terminate(self, additional_data, error_code, last_stream_id):
        self.src_conn.send_terminate(
            error_code=error_code,
            additional_data=additional_data,
            last_stream_id=last_stream_id)


class Stream(object):
    def __init__(self, layer, context, stream_id):
        self.layer = layer
        self.context = context
        self.stream_id = stream_id
        self.request = None
        self.response = None

    def on_request(self, request, **kwargs):
        plugin_result = self.layer.interceptor.request(
            layer_context=self.context, request=request)

        self.request = plugin_result.request if plugin_result else request
        self.layer.dest_conn.send_request(
            self.stream_id, self.request, **kwargs)

    def on_push(self, request, parent_stream_id):
        plugin_result = self.layer.interceptor.request(
            layer_context=self.context, request=request)

        self.request = plugin_result.request if plugin_result else request
        self.layer.src_conn.send_pushed_stream(
            parent_stream_id, self.stream_id, self.request)

    def on_response(self, response):
        plugin_result = self.layer.interceptor.response(
            layer_context=self.context,
            request=self.request, response=response
        )

        self.response = plugin_result.response if plugin_result else response
        self.layer.src_conn.send_response(
            self.stream_id, self.response)
