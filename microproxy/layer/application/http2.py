from tornado import concurrent, gen

from microproxy.protocol.http2 import Connection
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
            self.context.src_stream, client_side=False,
            conn_type="source",
            on_request=self.on_request,
            on_settings=self.on_src_settings,
            on_window_updates=self.on_src_window_updates,
            on_priority_updates=self.on_src_priority_updates,
            on_reset=self.on_src_reset,
            readonly=context.config["mode"] == "replay")
        self.dest_conn = Connection(
            self.context.dest_stream, client_side=True,
            conn_type="destination",
            on_response=self.on_response,
            on_push=self.on_push,
            on_settings=self.on_dest_settings,
            on_window_updates=self.on_dest_window_updates,
            on_priority_updates=self.on_dest_priority_updates,
            on_reset=self.on_dest_reset)
        self.streams = dict()
        self.src_to_dest_ids = dict([(0, 0)])
        self.dest_to_src_ids = dict([(0, 0)])
        self._future = concurrent.Future()

    @gen.coroutine
    def process_and_return_context(self):
        yield self._init_h2_connection()
        self.context.src_stream.read_until_close(
            streaming_callback=self.src_conn.receive)
        self.context.src_stream.set_close_callback(self.on_src_close)

        self.context.dest_stream.read_until_close(
            streaming_callback=self.dest_conn.receive)
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

    def update_ids(self, src_stream_id, dest_stream_id):
        self.src_to_dest_ids[src_stream_id] = dest_stream_id
        self.dest_to_src_ids[dest_stream_id] = src_stream_id

    def on_request(self, stream_id, request, priority_updated):
        dest_stream_id = self.dest_conn.get_next_available_stream_id()
        self.update_ids(stream_id, dest_stream_id)

        if priority_updated:
            priority_weight = priority_updated.weight
            priority_exclusive = priority_updated.exclusive
            priority_depends_on = self.safe_mapping_id(
                self.src_to_dest_ids, priority_updated.depends_on)
        else:
            priority_weight = None
            priority_exclusive = None
            priority_depends_on = None

        stream = Stream(self, self.context, stream_id, dest_stream_id)
        stream.on_request(
            request,
            priority_weight=priority_weight,
            priority_exclusive=priority_exclusive,
            priority_depends_on=priority_depends_on)
        self.streams[stream_id] = stream

    def on_push(self, pushed_stream_id, parent_stream_id, request):
        self.update_ids(pushed_stream_id, pushed_stream_id)
        target_parent_stream_id = self.dest_to_src_ids[parent_stream_id]

        stream = Stream(self, self.context, pushed_stream_id, pushed_stream_id)
        stream.on_push(request, target_parent_stream_id)
        self.streams[pushed_stream_id] = stream

    def on_response(self, stream_id, response):
        src_stream_id = self.dest_to_src_ids[stream_id]
        self.streams[src_stream_id].on_response(response)

        self.on_finish(src_stream_id)

    def on_finish(self, src_stream_id):
        stream = self.streams[src_stream_id]

        self.context.interceptor.publish(
            layer_context=self.context, request=stream.request,
            response=stream.response)
        del self.streams[src_stream_id]

        if self.context.config["mode"] == "replay":
            self.context.src_stream.close()
            self.context.dest_stream.close()

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

    def on_src_window_updates(self, stream_id, delta):
        target_stream_id = self.safe_mapping_id(self.src_to_dest_ids, stream_id)
        self.dest_conn.send_window_updates(target_stream_id, delta)

    def on_dest_window_updates(self, stream_id, delta):
        target_stream_id = self.safe_mapping_id(self.dest_to_src_ids, stream_id)
        self.src_conn.send_window_updates(target_stream_id, delta)

    def on_src_priority_updates(self, stream_id, depends_on,
                                weight, exclusive):
        target_stream_id = self.safe_mapping_id(
            self.src_to_dest_ids, stream_id)
        target_depends_on = self.safe_mapping_id(
            self.src_to_dest_ids, depends_on)
        if target_stream_id and target_depends_on:
            self.dest_conn.send_priority_updates(
                target_stream_id, target_depends_on, weight, exclusive)

    def on_dest_priority_updates(self, stream_id, depends_on,
                                 weight, exclusive):
        target_stream_id = self.safe_mapping_id(
            self.dest_to_src_ids, stream_id)
        target_depends_on = self.safe_mapping_id(
            self.dest_to_src_ids, depends_on)
        if target_stream_id and target_depends_on:
            self.src_conn.send_priority_updates(
                target_stream_id, target_depends_on, weight, exclusive)

    def safe_mapping_id(self, ids, stream_id):
        if stream_id in ids:
            return ids[stream_id]
        return 0

    def on_src_reset(self, stream_id, error_code):
        target_stream_id = self.src_to_dest_ids[stream_id]
        if error_code == 0x8:
            self.dest_conn.send_reset(target_stream_id, error_code)

    def on_dest_reset(self, stream_id, error_code):
        target_stream_id = self.dest_to_src_ids[stream_id]
        if error_code == 0x8:
            self.src_conn.send_reset(target_stream_id, error_code)


class Stream(object):
    def __init__(self, layer, context, src_stream_id, dest_stream_id):
        self.layer = layer
        self.context = context
        self.src_stream_id = src_stream_id
        self.dest_stream_id = dest_stream_id
        self.request = None
        self.response = None

    def on_request(self, request, **kwargs):
        plugin_ressult = self.context.interceptor.request(
            layer_context=self.context, request=request)

        self.request = plugin_ressult.request if plugin_ressult else request
        self.layer.dest_conn.send_request(
            self.dest_stream_id, self.request, **kwargs)

    def on_push(self, request, parent_stream_id):
        plugin_ressult = self.context.interceptor.request(
            layer_context=self.context, request=request)

        self.request = plugin_ressult.request if plugin_ressult else request
        self.layer.src_conn.send_pushed_stream(
            parent_stream_id, self.src_stream_id, self.request)

    def on_response(self, response):
        plugin_result = self.context.interceptor.response(
            layer_context=self.context,
            request=self.request, response=response
        )

        self.response = plugin_result.response if plugin_result else response
        self.layer.src_conn.send_response(
            self.src_stream_id, self.response)
