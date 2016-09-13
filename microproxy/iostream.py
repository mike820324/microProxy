import errno
from tornado import ioloop
from tornado.iostream import IOStream, SSLIOStream, StreamClosedError
from tornado.concurrent import TracebackFuture
from OpenSSL import SSL
from service_identity import VerificationError
from service_identity.pyopenssl import verify_hostname

from microproxy.utils import get_logger

logger = get_logger(__name__)


def safe_resume_stream(src_stream):
    if isinstance(src_stream, MicroProxyIOStream) and src_stream.is_pause:
        src_stream.resume()


class MicroProxyIOStream(IOStream):
    def __init__(self, sock, **kwargs):
        super(MicroProxyIOStream, self).__init__(sock, **kwargs)
        self.is_pause = False

    def pause(self):
        self.socket.setblocking(True)
        self._state = None
        self.io_loop.remove_handler(self.socket)
        self.is_pause = True

    def resume(self):
        self.socket.setblocking(False)
        self._add_io_state(ioloop.IOLoop.READ)
        self._add_io_state(ioloop.IOLoop.WRITE)
        self.is_pause = False

    def detach(self):
        if (self._read_callback or self._read_future or
                self._write_callback or self._write_future or
                self._connect_callback or self._connect_future or
                self._pending_callbacks or self._closed or
                self._read_buffer or self._write_buffer):
            raise ValueError("IOStream is not idle; cannot detach")
        _socket = self.socket
        self.io_loop.remove_handler(_socket)
        self.socket = None
        return _socket

    def start_tls(self, server_side, ssl_options, server_hostname=None):
        if not isinstance(ssl_options, SSL.Context):
            raise ValueError("ssl_options is not SSL.Context")

        _socket = self.detach()
        _socket = SSL.Connection(ssl_options, _socket)
        if server_side:
            _socket.set_accept_state()
        else:
            _socket.set_connect_state()

        orig_close_callback = self._close_callback
        self._close_callback = None

        future = TracebackFuture()
        ssl_stream = MicroProxySSLIOStream(_socket,
                                           server_hostname,
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
    def __init__(self, sock, server_hostname=None, **kwargs):
        super(MicroProxySSLIOStream, self).__init__(sock, **kwargs)
        self._server_hostname = unicode(server_hostname) if server_hostname else None

    def _handle_connect(self):
        super(SSLIOStream, self)._handle_connect()
        if self.closed():
            return
        self.io_loop.remove_handler(self.socket)
        old_state = self._state
        self._state = None
        self.socket = SSL.Connection(self._ssl_options, self.socket)
        self.socket.set_connect_state()
        self._add_io_state(old_state)

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

        except SSL.SysCallError as e:
            err_num = abs(e[0])
            if err_num in (errno.EBADF, errno.ENOTCONN, errno.EPERM):
                return self.close(exc_info=True)

            raise

        except SSL.Error as err:
            try:
                peer = self.socket.getpeername()
            except Exception:
                peer = '(not connected)'
                logger.warning("SSL Error on %s %s: %s",
                               self.socket.fileno(), peer, err)
            return self.close(exc_info=True)

        except AttributeError:
            return self.close(exc_info=True)

        else:
            self._ssl_accepting = False
            verify_mode = self.socket.get_context().get_verify_mode()
            if (verify_mode != SSL.VERIFY_NONE and
                    self._server_hostname is not None):
                try:
                    verify_hostname(self.socket, self._server_hostname)
                except VerificationError as e:
                    logger.warning("Invalid SSL certificate: {0}".format(e))
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
            return None
        try:
            chunk = self.socket.read(self.read_chunk_size)
        except SSL.WantReadError:
            return None

        except SSL.ZeroReturnError:
            self.close(exc_info=True)
            return None

        except SSL.SysCallError as e:
            err_num = abs(e[0])
            if err_num in (errno.EWOULDBLOCK, errno.EAGAIN):
                return None

            # NOTE: We will handle the self.close in here.
            # _read_to_buffer of BaseIOStream will not chceck SSL.SysCallError
            if err_num == errno.EPERM:
                self.close(exc_info=True)
                return None

            self.close(exc_info=True)
            raise

        # NOTE: Just in case we missed some SSL Error type.
        except SSL.Error as e:
            raise

        if not chunk:
            self.close()
            return None
        return chunk
