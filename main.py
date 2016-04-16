import struct
import socket
import datetime, time
import tornado.ioloop
import tornado.tcpserver
import tornado.iostream

from http import HttpRequest, HttpResponse

import logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class HttpLayer(object):
    '''
    HTTPServer: HTTPServer will handle http trafic.
    '''
    def __init__(self, target_src_stream, target_dest_stream):
        super(HttpLayer, self).__init__()
        self.http_request = HttpRequest()
        self.http_response = HttpResponse()

        self.is_src_close = False
        self.target_src_stream = target_src_stream
        self.target_src_stream.read_until_close(streaming_callback=self.on_request)
        self.target_src_stream.set_close_callback(self.on_src_close)

        self.is_dest_close = False
        self.dest_ip = target_dest_stream.socket.getpeername()[0]
        self.target_dest_stream = target_dest_stream
        self.target_dest_stream.read_until_close(streaming_callback=self.on_response)
        self.target_dest_stream.set_close_callback(self.on_dest_close)

    def on_src_close(self):
        # fixme: need better error handling
        pass

    def on_dest_close(self):
        # fixme: need better error handling
        pass

    def on_request(self, data):
        self.http_request.parse(data)
        if self.http_request.is_done and not self.target_dest_stream.closed():
            __data = self.http_request.serialize()
            self.http_request.deserialize(__data)
            self.target_dest_stream.write(self.http_request.data)
            self.http_request.clear()

    def on_response(self, data):
        self.http_response.parse(data)
        if self.http_response.is_done and not self.target_src_stream.closed():
            current_time = datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S')
            # wait for zmq reply
            for chunk in self.http_response.data:
                try:
                    self.target_src_stream.write(chunk)
                except tornado.iostream.StreamClosedError(real_error):
                    self.on_src_close()
            logger.info("{0} : {1} {2} {3} {4}".format(current_time, self.dest_ip, self.http_response.status, self.http_request.method, self.http_request.url))
            self.http_response.clear()
            logger.info(self.http_response.serialize())

class TLSLayer(object):
    '''
    TLSLayer: passing all the src data to destination. Will not intercept anything
    '''
    def __init__(self, target_src_stream, target_dest_stream):
        super(TLSLayer, self).__init__()
        self.is_tls = None

        self.is_src_close = False
        self.target_src_stream = target_src_stream
        self.target_src_stream.read_until_close(streaming_callback=self.on_request)
        self.target_src_stream.set_close_callback(self.on_src_close)

        self.is_dest_close = False
        self.dest_ip = target_dest_stream.socket.getpeername()[0] 
        self.target_dest_stream = target_dest_stream
        self.target_dest_stream.read_until_close(streaming_callback=self.on_response)
        self.target_dest_stream.set_close_callback(self.on_dest_close)

    def is_tls_protocol(self, data):
        return (
            data[0] == '\x16' and
            data[1] == '\x03' and
            data[2] in ('\x00', '\x01', '\x02', '\x03')
        )

    def on_src_close(self):
        self.is_src_close = True

    def on_dest_close(self):
        self.is_dest_close = True

    def on_request(self, data):
        if not self.is_dest_close:
            self.target_dest_stream.write(data)

    def on_response(self, data):
        if not self.is_src_close:
            self.target_src_stream.write(data)

class DirectServer(object):
    '''
    DirectServer: passing all the src data to destination. Will not intercept anything
    '''
    def __init__(self, target_src_stream, target_dest_stream):
        super(DirectServer, self).__init__()

        self.is_src_close = False
        self.target_src_stream = target_src_stream
        self.target_src_stream.read_until_close(streaming_callback=self.on_request)
        self.target_src_stream.set_close_callback(self.on_src_close)

        self.is_dest_close = False
        self.dest_ip = target_dest_stream.socket.getpeername()[0]
        self.target_dest_stream = target_dest_stream
        self.target_dest_stream.read_until_close(streaming_callback=self.on_response)
        self.target_dest_stream.set_close_callback(self.on_dest_close)

    def on_src_close(self):
        self.is_src_close = True

    def on_dest_close(self):
        self.is_dest_close = True

    def on_request(self, data):
        if not self.is_dest_close:
            self.target_dest_stream.write(data)

    def on_response(self, data):
        if not self.is_src_close:
            self.target_src_stream.write(data)

class SocksLayer(object):
    def __init__(self, stream):
        super(SocksLayer, self).__init__()
        self.request_data = None
        self.src_stream = stream
        self.src_stream.read_bytes(3, self.on_socks_greeting)
        self.dest_stream = None
    
    def on_socks_greeting(self, data):
        logger.info("socks greeting to {0}".format(self.src_stream.socket.getpeername()[0]))
        socks_init_data = struct.unpack('BBB', data)
        socks_version = socks_init_data[0]
        socks_nmethod = socks_init_data[1]
        socks_methods = socks_init_data[2]
    
        if socks_nmethod != 1: 
            logger.warning("SOCKS5 Auth not supported")
            self.src_stream.close()
        else: 
            response = struct.pack('BB', 5, 0)
            self.src_stream.write(response)
            self.src_stream.read_bytes(10, self.on_socks_request)

    def on_socks_request(self, data):
        self.request_data = struct.unpack('!BBxBIH', data)
        socks_version = self.request_data[0]
        socks_cmd = self.request_data[1]
        socks_atyp = self.request_data[2]
        socks_dest_addr = socket.inet_ntoa(struct.pack('!I', self.request_data[3]))
        socks_dest_port = self.request_data[4]
        logger.info("socks request to {0}:{1}".format(socks_dest_addr, socks_dest_port))

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
        self.dest_stream = tornado.iostream.IOStream(s)
        self.dest_stream.connect((socks_dest_addr, socks_dest_port), self.on_dest_connect)

    def on_dest_connect(self):
        socks_dest_port = self.request_data[4]
        response = struct.pack('!BBxBIH', 5, 0, 1, self.request_data[-2], self.request_data[-1])
        self.src_stream.write(response)

        # fixme: Determine in runtime.
        if socks_dest_port == 5000 or socks_dest_port == 80:
            HttpLayer(self.src_stream, self.dest_stream)

        elif socks_dest_port == 5001 or socks_dest_port == 443:
            TLSLayer(self.src_stream, self.dest_stream)

        else:
            DirectServer(self.src_stream, socks_dest_stream)

class ProxyServer(tornado.tcpserver.TCPServer):
    def __init__(self):
        super(ProxyServer, self).__init__()

    def handle_stream(self, stream, port):
        SocksLayer(stream)

def main():
    server = ProxyServer()

    # fixme: use options
    server.listen(5580, "127.0.0.1")

    try:
        tornado.ioloop.IOLoop.instance().start()
    except KeyboardInterrupt:
        logger.info("bye")

if __name__ == "__main__":
    main()
