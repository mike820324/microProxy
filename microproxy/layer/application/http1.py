from tornado import concurrent

import h11
from h11 import Connection as H11Connection
from h11 import Request, InformationalResponse, Response, Data, EndOfMessage

from microproxy.utils import get_logger
logger = get_logger(__name__)


class Http1Layer(object):
    def __init__(self, context):
        super(Http1Layer, self).__init__()
        self.context = context
        self.src_conn = Connection(
            self.context.src_stream, self.context.dest_stream, False,
            self, our_role=h11.SERVER)
        self.dest_conn = Connection(
            self.context.dest_stream, self.context.src_stream, True,
            self, our_role=h11.CLIENT)
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


class Connection(H11Connection):
    def __init__(self, from_stream, to_stream, is_server, layer, *args, **kwargs):
        super(Connection, self).__init__(*args, **kwargs)
        self.from_stream = from_stream
        self.to_stream = to_stream
        self._type = "dest" if is_server else "src"
        self.layer = layer

    def on_data_received(self, data):
        try:
            self.to_stream.write(data)
            self.receive_data(data)
            event = self.next_event()
            if event != h11.NEED_DATA:
                if isinstance(event, Request):
                    logger.info("Receiving Request")
                if isinstance(event, InformationalResponse):
                    logger.info("Receiving Informaton Response")
                if isinstance(event, Response):
                    logger.info("Receiving Response")
                if isinstance(event, Data):
                    logger.info("Receiving Data")
                if isinstance(event, EndOfMessage):
                    logger.info("Receiving End of Message")

        except Exception as e:
            logger.error("Exception on {0}".format(self._type))
            logger.exception(e)
