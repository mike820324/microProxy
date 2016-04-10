import struct
import socket
import tornado.ioloop
import tornado.tcpserver
import tornado.tcpclient
import tornado.iostream

from http_parser.parser import HttpParser
from gzip import GzipFile
from StringIO import StringIO

class HttpMessage(object):
    def __init__(self):
        super(HttpMessage, self).__init__()
        self.raw_data = b""
        self.header = None
        self.body = None
        self.parser = HttpParser()
    
    def clear(self):
        self.raw_data = b""
        self.parser = HttpParser()

    def read(self, data):
        self.raw_data += data

        self.parser.execute(data, len(data))
        if self.parser.is_message_complete():
            self.header = self.parser.get_headers()
            self.body = self.parser.recv_body()
            print "src -> dest"
            print "http header"
            headers = self.parser.get_headers()
            for header in headers:
                print "{0} : {1}".format(header, headers[header])
            return self.raw_data

        return None

class HttpServer(object):
    '''
    HTTPServer: HTTPServer will handle http trafic.
    '''
    def __init__(self, target_src_stream, target_dest_host, target_dest_port):
        super(HttpServer, self).__init__()
        self.http_message = HttpMessage()

        self.target_src_stream = target_src_stream
        self.target_src_stream.read_until_close(streaming_callback=self.on_request)

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
        self.target_dest_stream = tornado.iostream.IOStream(s)
        self.target_dest_stream.connect((target_dest_host, target_dest_port))
        self.target_dest_stream.read_until_close(streaming_callback=self.on_response)

    def on_request(self, data):
        raw_data = self.http_message.read(data)
        if raw_data is not None:
            self.target_dest_stream.write(raw_data)
            self.http_message.clear()

    def on_response(self, data):
        raw_data = self.http_message.read(data)
        if raw_data is not None:
            # sio = StringIO(self.http_message.body)
            # gz = GzipFile(fileobj=sio, mode="rb")
            # print gz.read()
            self.target_src_stream.write(raw_data)
            self.http_message.clear()

class TLSServer(object):
    def __init__(self, target_src_stream, target_dest_host, target_dest_port):
        super(DirectServer, self).__init__()

        self.target_src_stream = target_src_stream
        self.target_src_stream.read_until_close(streaming_callback=self.on_request)

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
        self.target_dest_stream = tornado.iostream.IOStream(s)
        self.target_dest_stream.connect((target_dest_host, target_dest_port))
        self.target_dest_stream.read_until_close(streaming_callback=self.on_response)

    def on_request(self, data):
        self.target_dest_stream.write(data)

    def on_response(self, data):
        self.target_src_stream.write(data)

class DirectServer(object):
    '''
    DirectServer: passing all the src data to destination. Will not intercept anything
    '''
    def __init__(self, target_src_stream, target_dest_host, target_dest_port):
        super(DirectServer, self).__init__()

        self.target_src_stream = target_src_stream
        self.target_src_stream.read_until_close(streaming_callback=self.on_request)

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
        self.target_dest_stream = tornado.iostream.IOStream(s)
        self.target_dest_stream.connect((target_dest_host, target_dest_port))
        self.target_dest_stream.read_until_close(streaming_callback=self.on_response)

    def on_request(self, data):
        self.target_dest_stream.write(data)

    def on_response(self, data):
        self.target_src_stream.write(data)

class SocksServer(object):
    def __init__(self, stream):
        super(SocksServer, self).__init__()
        self.stream = stream
        self.stream.read_bytes(3, self.on_socks_greeting)
    
    def on_socks_greeting(self, data):
        print "socks client greeting"
        socks_init_data = struct.unpack('BBB', data)
        socks_version = socks_init_data[0]
        socks_nmethod = socks_init_data[1]
        socks_methods = socks_init_data[2]
    
        # Auth is not supported
        if socks_nmethod != 1:
            print "Auth not supported"
        
        response = struct.pack('BB', 5, 0)
        self.stream.write(response)
        self.stream.read_bytes(10, self.on_socks_request)

    def on_socks_request(self, data):
        print "socks client request"
        socks_init_data = struct.unpack('!BBxBIH', data)
        socks_version = socks_init_data[0]
        socks_cmd = socks_init_data[1]
        socks_atyp = socks_init_data[2]
        socks_dest_addr = socks_init_data[3]
        socks_dest_port = socks_init_data[4]

        socks_version = 5 # socks 5
        socks_status = 0 # Success
        socks_connection_type = 1 #IPV4
        response = struct.pack('!BBxBIH', 5, 0, 1, socks_init_data[-2], socks_init_data[-1])
        self.stream.write(response)

        print "socks -> http"
        print "{0}:{1}".format(socket.inet_ntoa(struct.pack('!I', socks_dest_addr)), socks_dest_port)

        if socks_dest_port == 80:
            HttpServer(self.stream, socket.inet_ntoa(struct.pack('!I', socks_dest_addr)), socks_dest_port)
        else:
            DirectServer(self.stream, socket.inet_ntoa(struct.pack('!I', socks_dest_addr)), socks_dest_port)

class ProxyServer(tornado.tcpserver.TCPServer):
    def __init__(self):
        super(ProxyServer, self).__init__()

    def handle_stream(self, stream, port):
        SocksServer(stream)

def main():
    server = ProxyServer()
    server.listen(5580, "127.0.0.1")
    tornado.ioloop.IOLoop.instance().start()

main()
