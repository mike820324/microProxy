from tornado.iostream import IOStream, SSLIOStream, StreamClosedError
from tornado.concurrent import TracebackFuture
import socket
from OpenSSL import SSL

import errno
_ERRNO_WOULDBLOCK = (errno.EWOULDBLOCK, errno.EAGAIN)

class MicroProxyIOStream(IOStream):
    def __init__(self, sock, **kwargs):
        super(MicroProxyIOStream, self).__init__(sock, **kwargs)

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
        # Based on code from test_ssl.py in the python stdlib
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

        except socket.error as err:
            # Some port scans (e.g. nmap in -sT mode) have been known
            # to cause do_handshake to raise EBADF and ENOTCONN, so make
            # those errors quiet as well.
            # https://groups.google.com/forum/?fromgroups#!topic/python-tornado/ApucKJat1_0
            if (self._is_connreset(err) or
                    err.args[0] in (errno.EBADF, errno.ENOTCONN)):
                return self.close(exc_info=True)
            raise
        except AttributeError:
            # On Linux, if the connection was reset before the call to
            # wrap_socket, do_handshake will fail with an
            # AttributeError.
            return self.close(exc_info=True)
        else:
            self._ssl_accepting = False
            # if not self._verify_cert(self.socket.get_peer_cert()):
            #     self.close()
            #     return
            self._run_ssl_connect_callback()

    def _verify_cert(self, peercert):
        pass
        # if isinstance(self._ssl_options, dict):
        #     verify_mode = self._ssl_options.get('cert_reqs', ssl.CERT_NONE)
        # elif isinstance(self._ssl_options, ssl.SSLContext):
        #     verify_mode = self._ssl_options.verify_mode
        # assert verify_mode in (ssl.CERT_NONE, ssl.CERT_REQUIRED, ssl.CERT_OPTIONAL)
        # if verify_mode == ssl.CERT_NONE or self._server_hostname is None:
        #     return True
        # cert = self.socket.getpeercert()
        # if cert is None and verify_mode == ssl.CERT_REQUIRED:
        #     gen_log.warning("No SSL certificate given")
        #     return False
        # try:
        #     ssl_match_hostname(peercert, self._server_hostname)
        # except SSLCertificateError as e:
        #     gen_log.warning("Invalid SSL certificate: %s" % e)
        #     return False
        # else:
        #     return True

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
            if e.args[0] in _ERRNO_WOULDBLOCK:
                return None
            else:
                raise
        if not chunk:
            self.close()
            return None
        return chunk
