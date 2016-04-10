import struct
import socket
import tornado.ioloop
import tornado.tcpserver
import tornado.tcpclient
import tornado.iostream

from http import HttpRequest, HttpResponse

class HttpServer(object):
    '''
    HTTPServer: HTTPServer will handle http trafic.
    '''
    def __init__(self, target_src_stream, target_dest_host, target_dest_port):
        super(HttpServer, self).__init__()
        self.http_request = HttpRequest()
        self.http_response = HttpResponse()

        self.target_src_stream = target_src_stream
        self.target_src_stream.read_until_close(streaming_callback=self.on_request)

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
        self.target_dest_stream = tornado.iostream.IOStream(s)
        self.target_dest_stream.connect((target_dest_host, target_dest_port))
        self.target_dest_stream.read_until_close(streaming_callback=self.on_response)

    def on_request(self, data):
        self.http_request.parse(data)
        if self.http_request.is_done:
            print "src -> dest"
            try:
                self.http_request.header["Accept-Encoding"] = "gzip, deflate"
            except KeyError:
                print " no such header"

            self.target_dest_stream.write(self.http_request.data)
            self.http_request.clear()

    def on_response(self, data):
        self.http_response.parse(data)
        if self.http_response.is_done:
            print "dest -> src"
            self.target_src_stream.write(self.http_response.data)
            self.http_response.clear()

class TLSServer(object):
    def __init__(self, target_src_stream, target_dest_host, target_dest_port):
        super(TLSServer, self).__init__()

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

class SocksLayer(object):
    def __init__(self, stream):
        super(SocksLayer, self).__init__()
        self.stream = stream
        self.stream.read_bytes(3, self.on_socks_greeting)
    
    def on_socks_greeting(self, data):
        print "socks client greeting"
        socks_init_data = struct.unpack('BBB', data)
        socks_version = socks_init_data[0]
        socks_nmethod = socks_init_data[1]
        socks_methods = socks_init_data[2]
    
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
        SocksLayer(stream)

def main():
    server = ProxyServer()
    server.listen(5580, "127.0.0.1")
    tornado.ioloop.IOLoop.instance().start()

main()
