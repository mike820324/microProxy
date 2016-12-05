import errno
import socket
from tornado.iostream import IOStream, SSLIOStream, StreamClosedError, UnsatisfiableReadError
from tornado.log import gen_log
from tornado.concurrent import TracebackFuture
from OpenSSL import SSL
from service_identity import VerificationError
from service_identity.pyopenssl import verify_hostname

from microproxy.log import ProxyLogger

logger = ProxyLogger.get_logger(__name__)


class MicroProxyIOStream(IOStream):
    def __init__(self, sock, **kwargs):
        super(MicroProxyIOStream, self).__init__(sock, **kwargs)

    def _handle_events(self, fd, events):
        if self.closed():
            gen_log.warning("Got events for closed stream %s", fd)
            return
        try:
            if self._connecting:
                self._handle_connect()
            if self.closed():
                return
            if events & self.io_loop.READ:
                # NOTE: We use explict read instead of implicit.
                # The reason IOStream is not idle is that when an event happened,
                # tornado iostream will still try to read them into buffer.
                # Our approach is that when someone is trying to read the iostream,
                # we will read it.
                if self._should_socket_close() or self.reading():
                    self._handle_read()

            if self.closed():
                return
            if events & self.io_loop.WRITE:
                self._handle_write()
            if self.closed():
                return
            if events & self.io_loop.ERROR:
                self.error = self.get_fd_error()
                self.io_loop.add_callback(self.close)
                return
            state = self.io_loop.ERROR
            if self.reading():
                state |= self.io_loop.READ
            if self.writing():
                state |= self.io_loop.WRITE
            if state == self.io_loop.ERROR and self._read_buffer_size == 0:
                state |= self.io_loop.READ
            if state != self._state:
                assert self._state is not None, \
                    "shouldn't happen: _handle_events without self._state"
                self._state = state
                self.io_loop.update_handler(self.fileno(), self._state)
        except UnsatisfiableReadError as e:
            gen_log.info("Unsatisfiable read, closing connection: %s" % e)
            self.close(exc_info=True)
        except Exception:
            gen_log.error("Uncaught exception, closing connection.",
                          exc_info=True)
            self.close(exc_info=True)
            raise

    def _should_socket_close(self):
        _data = self.socket.recv(1, socket.MSG_PEEK)
        return len(_data) == 0

    def peek(self, length):
        """Peek into the underline socket buffer.

        Args:
            length (int): The peeking buffer length.

        Returns:
            (bytes): Bytes of buffer.

        Raises:
            ValueError: If length is not int and smaller than one
            will raise ValueError.
        """
        if not isinstance(length, int) or length < 0:
            raise ValueError("Incorrect length.")

        # TODO: Change into nonblocking mode.
        self.socket.setblocking(True)
        while True:
            try:
                _data = self.socket.recv(length, socket.MSG_PEEK)
            except socket.error:
                continue
            except:
                raise
            else:
                return _data
            finally:
                self.socket.setblocking(False)

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
        self._closed = True
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
            if server_hostname:
                _socket.set_tlsext_host_name(server_hostname.encode("idna"))

        orig_close_callback = self._close_callback
        self._close_callback = None

        future = TracebackFuture()
        ssl_stream = MicroProxySSLIOStream(_socket,
                                           server_hostname=server_hostname,
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
                    self.close(exc_info=True)
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
