from tornado.log import app_log
from tornado import tcpserver
from iostream import MicroProxyIOStream


class TCPServer(tcpserver.TCPServer):
    """tornado TCPServer that use the extended iostream and ssliostream."""
    def __init__(self, **kwargs):
        super(TCPServer, self).__init__(**kwargs)

    def _handle_connection(self, connection, address):
        """Handle connection with extended IOStream.

        In order to let the later start_tls works properly,
        the _handle_connection must use extened IOStream to create the proper ssl context.

        NOTE: currently, we only use IOStream. That is if you pass ssl_options in contructor,
        it will still use IOStream and not SSLIOStream.
        """
        try:
            stream = MicroProxyIOStream(connection,
                                        io_loop=self.io_loop,
                                        max_buffer_size=self.max_buffer_size,
                                        read_chunk_size=self.read_chunk_size)
            future = self.handle_stream(stream)
            if future is not None:
                self.io_loop.add_future(future, lambda f: f.result())

        except Exception:
            app_log.error("Error in connection callback", exc_info=True)
