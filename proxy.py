import struct
import socket
import json
import datetime, time
import ConfigParser

import zmq
from zmq.eventloop import ioloop, zmqstream
ioloop.install()

import tornado.tcpserver
import tornado.iostream

from http import HttpRequest, HttpResponse

import logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class AbstractServer(object):
    def __init__(self, target_src_stream, dest_stream):
        super(AbstractServer, self).__init__()
        self.target_src_stream = target_src_stream
        self.target_dest_stream = dest_stream

    def start_server(self):
        logger.info("{0} socket is ready for process the request".format(__name__))
        self.is_src_close = False
        self.target_src_stream.read_until_close(streaming_callback=self.on_request)
        self.target_src_stream.set_close_callback(self.on_src_close)

        self.is_dest_close = False
        self.target_dest_stream.read_until_close(streaming_callback=self.on_response)
        self.target_dest_stream.set_close_callback(self.on_dest_close)

    def on_src_close(self):
        raise NotImplementedError

    def on_dest_close(self):
        raise NotImplementedError

    def on_request(self, data):
        raise NotImplementedError

    def on_response(self, data):
        raise NotImplementedError

class HttpLayer(AbstractServer):
    CONNECT = 0
    REQUEST_IN = 1
    REQUEST_OUT = 2
    RESPONSE_IN = 3
    RESPONSE_OUT = 4

    '''
    HTTPServer: HTTPServer will handle http trafic.
    '''
    def __init__(self, target_src_stream, dest_stream):
        super(HttpLayer, self).__init__(target_src_stream, dest_stream)
        self.state = self.CONNECT
        self.http_request = HttpRequest()
        self.http_response = HttpResponse()
        self.zmq_stream = self.create_zmq_stream()

    def on_src_close(self):
        # fixme: need better error handling
        pass

    def on_dest_close(self):
        # fixme: need better error handling
        pass

    def create_zmq_stream(self):
        parser = ConfigParser.SafeConfigParser()
        parser.read("application.cfg")
        host = parser.get("ConnectionController", "zmq.host")
        port = parser.get("ConnectionController", "zmq.port")

        zmq_context = zmq.Context()
        zmq_socket = zmq_context.socket(zmq.REQ)
        # fixme: use unix domain socket instead of tcp
        zmq_socket.connect("tcp://{0}:{1}".format(host, port))
        zmq_stream = zmqstream.ZMQStream(zmq_socket)
        zmq_stream.on_recv(self.on_zmq_recv)
        return zmq_stream

    def on_zmq_recv(self, str_data):
        data = json.loads(str_data[0])
        if self.state == self.REQUEST_IN:
            logger.debug("request out")
            self.http_request.deserialize(data["req_data"])
            self.target_dest_stream.write(self.http_request.data)
            self.http_request.clear()
            self.state = self.REQUEST_OUT

        elif self.state == self.RESPONSE_IN:
            logger.debug("response out")
            self.http_response.deserialize(data["resp_data"])
            for chunk in self.http_response.data:
                try:
                    self.target_src_stream.write(chunk)
                except tornado.iostream.StreamClosedError(real_error):
                    self.on_src_close()
            self.http_response.clear()
            self.state = self.RESPONSE_OUT

    def on_request(self, data):
        logger.debug("request in")
        self.state = self.REQUEST_IN
        self.http_request.parse(data)
        if self.http_request.is_done and not self.target_dest_stream.closed():
            logger.debug("request in complete")
            __data = {
                "type": "request",
                "req_data": self.http_request.serialize(),
                "resp_data": self.http_response.serialize()
            }
            self.zmq_stream.send_json(__data)

    def on_response(self, data):
        logger.debug("response in")
        self.state = self.RESPONSE_IN
        self.http_response.parse(data)
        if self.http_response.is_done and not self.target_src_stream.closed():
            logger.debug("request out complete")
            __data = {
                "type": "response",
                "req_data": self.http_request.serialize(),
                "resp_data": self.http_response.serialize()
            }
            self.zmq_stream.send_json(__data)

class TLSLayer(AbstractServer):
    '''
    TLSLayer: passing all the src data to destination. Will not intercept anything
    '''
    def __init__(self, target_src_stream, dest_host, dest_port):
        super(TLSLayer, self).__init__(target_src_stream, dest_stream)
        self.is_tls = None

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

class DirectServer(AbstractServer):
    '''
    DirectServer: passing all the src data to destination. Will not intercept anything
    '''
    def __init__(self, target_src_stream, dest_host, dest_port):
        super(DirectServer, self).__init__(target_src_stream, dest_stream)

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
    STATE_INIT = "init"
    STATE_GREETED = "greeted"
    STATE_REQ = "request"
    STATE_READY = "ready"
    STATE_CLOSE = "close"

    def __init__(self, stream):
        super(SocksLayer, self).__init__()
        self.src_stream = stream
        self.state = self.STATE_INIT

    def read(self):
        if self.state == self.STATE_INIT:
            self.src_stream.read_bytes(3, self.on_socks_greeting)

        elif self.state == self.STATE_GREETED:
            self.src_stream.read_bytes(10, self.on_socks_request)

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
            self.state = self.STATE_GREETED
            self.read()

    def on_socks_request(self, data):
        request_data = struct.unpack('!BBxBIH', data)
        socks_version = request_data[0]
        socks_cmd = request_data[1]
        socks_atyp = request_data[2]
        socks_dest_addr = socket.inet_ntoa(struct.pack('!I', request_data[3]))
        socks_dest_port = request_data[4]
        logger.info("socks request to {0}:{1}".format(socks_dest_addr, socks_dest_port))


        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
        dest_stream = tornado.iostream.IOStream(s)

        def on_socks_ready():
            response = struct.pack('!BBxBIH', 5, 0, 1, request_data[-2], request_data[-1])
            self.src_stream.write(response)
            self.create_http_server(dest_stream, socks_dest_port).start_server()

        dest_stream.connect((socks_dest_addr, socks_dest_port), on_socks_ready)

    def create_http_server(self, dest_stream, dest_port):
        if dest_port == 5000 or dest_port == 80:
            return HttpLayer(self.src_stream, dest_stream)
        elif dest_port == 5001 or dest_port == 443:
            return TLSLayer(self.src_stream, dest_stream)
        else:
            return DirectServer(self.src_stream, dest_stream)

class ProxyServer(tornado.tcpserver.TCPServer):
    def __init__(self, host, port):
        super(ProxyServer, self).__init__()
        self.host = host
        self.port = port

    def handle_stream(self, stream, port):
        socks_layer = SocksLayer(stream)
        socks_layer.read()

    def start_listener(self):
        self.listen(self.port, self.host)
        logger.info("proxy server is listening at {0}:{1}".format(self.host, self.port))

def start_proxy_server(host, port):
    server = ProxyServer(host, port)
    server.start_listener()

    try:
        ioloop.IOLoop.instance().start()
    except KeyboardInterrupt:
        logger.info("bye")
