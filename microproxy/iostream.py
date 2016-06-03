import socket
import errno
from tornado import ioloop
from tornado.iostream import IOStream, SSLIOStream, StreamClosedError
from tornado.concurrent import TracebackFuture
from OpenSSL import SSL
from service_identity import VerificationError
from service_identity.pyopenssl import verify_hostname

from microproxy.utils import get_logger

logger = get_logger(__name__)


class MicroProxyIOStream(IOStream):
    def __init__(self, sock, **kwargs):
        super(MicroProxyIOStream, self).__init__(sock, **kwargs)

    def pause(self):
        self.socket.setblocking(True)
        self.io_loop.remove_handler(self.socket)

    def resume(self):
        self.socket.setblocking(False)
        self._add_io_state(ioloop.IOLoop.READ)
        self._add_io_state(ioloop.IOLoop.WRITE)

    def start_tls(self, server_side, ssl_options, server_hostname=None):
        if (self._read_callback or self._read_future or
                self._write_callback or self._write_future or
                self._connect_callback or self._connect_future or
                self._pending_callbacks or self._closed or
                self._read_buffer or self._write_buffer):
            raise ValueError("IOStream is not idle; cannot convert to SSL")

        if not isinstance(ssl_options, SSL.Context):
            raise ValueError("ssl_options is not SSL.Context")

        socket = self.socket
        self.io_loop.remove_handler(socket)
        self.socket = None
        socket = SSL.Connection(ssl_options, socket)
        if server_side:
            socket.set_accept_state()
        else:
            socket.set_connect_state()

        orig_close_callback = self._close_callback
        self._close_callback = None

        future = TracebackFuture()
        ssl_stream = MicroProxySSLIOStream(socket,
                                           ssl_options=ssl_options,
                                           io_loop=self.io_loop)

        def close_callback():
            if not future.done():
                future.set_exception(ssl_stream.error or StreamClosedError())
            if orig_close_callback is not None:
                orig_close_callback()

        ssl_stream.set_close_callback(close_callback)
        ssl_stream._ssl_connect_callback = lambda: future.set_result(ssl_stream)
        ssl_stream.max_buffer_size = self.max_buffer_size
        ssl_stream.read_chunk_size = self.read_chunk_size
        return future


class MicroProxySSLIOStream(SSLIOStream):
    def __init__(self, sock, **kwargs):
        super(MicroProxySSLIOStream, self).__init__(sock, **kwargs)

    def _do_ssl_handshake(self):
        try:
            self._handshake_reading = False
            self._handshake_writing = False
            self.socket.do_handshake()

        except SSL.WantReadError:
            self._handshake_reading = True
            return

        except SSL.WantWriteError:
            self._handshake_writing = True
            return

        except SSL.Error as err:
            try:
                peer = self.socket.getpeername()
            except Exception:
                peer = '(not connected)'
                logger.warning("SSL Error on %s %s: %s",
                               self.socket.fileno(), peer, err)
            return self.close(exc_info=True)

        except socket.error as err:
            if (self._is_connreset(err) or err.args[0] in (errno.EBADF, errno.ENOTCONN)):
                return self.close(exc_info=True)
            raise

        except AttributeError:
            return self.close(exc_info=True)
        else:
            self._ssl_accepting = False
            verify_mode = self.socket.get_context().get_verify_mode()
            if (verify_mode is not SSL.VERIFY_NONE and
                    self._server_hostname is not None):
                try:
                    verify_hostname(self.socket, self._server_hostname)
                except VerificationError as e:
                    logger.warning("Invalid SSL certificate: %s" % e)
                    self.close()
                    return

            self._run_ssl_connect_callback()

    def write_to_fd(self, data):
        try:
            return self.socket.send(data)
        except SSL.WantWriteError:
            return 0
        except SSL.Error:
            raise

    def read_from_fd(self):
        if self._ssl_accepting:
            # If the handshake hasn't finished yet, there can't be anything
            # to read (attempting to read may or may not raise an exception
            # depending on the SSL version)
            return None
        try:
            # SSLSocket objects have both a read() and recv() method,
            # while regular sockets only have recv().
            # The recv() method blocks (at least in python 2.6) if it is
            # called when there is nothing to read, so we have to use
            # read() instead.
            chunk = self.socket.read(self.read_chunk_size)
        except SSL.WantReadError:
            return None

        except SSL.Error:
                raise

        except socket.error as e:
            if e.args[0] in (errno.EWOULDBLOCK, errno.EAGAIN):
                return None
            else:
                raise
        if not chunk:
            self.close()
            return None
        return chunk
