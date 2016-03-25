import pyuv
import struct
import socket
import signal

from blinker import signal as blinker_signal
from http_parser.parser import HttpParser

def dump_hex(data):
    hex_str = ":".join(hex(ord(char)) for char in data)
    print(hex_str)

class HttpProtocol(object):
    def __init__(self):
        pass

class SocksProtocol(object):
    def __init__(self):
        pass

class ProxyClient(object):
    def __init__(self):
        self.uv_sock = pyuv.TCP(pyuv.Loop.default_loop())
        self.raw_data = ""

        self.is_socks_complete_signal = blinker_signal("complete")
        self.is_socks_complete_signal.connect(self.on_socks_complete, sender=self)
        self.is_socks_complete = False
        self.socks_protocol = SocksProtocol()

        self.http_protocol = HttpProtocol()
        self.http_parser = HttpParser()
        self.http_complete = False
        self.http_header = None
        self.http_body = []
    
    def on_socks_complete(self, sender):
        self.is_socks_complete = True

    def start_read(self):
        self.uv_sock.start_read(self.on_read)
    
    def on_read(self, client, data, error):
        if data is None:
            client.close()
            return

        if not self.is_socks_complete:
            if len(data) == 3:
                socks_init_data = struct.unpack('BBB', data)
                socks_version = socks_init_data[0]
                socks_nmethod = socks_init_data[1]
                socks_methods = socks_init_data[2]
                
                if socks_nmethod != 1:
                    client.close()
                    self.clients.remove(client)
                    print "Auth not supported"
                
                response = struct.pack('BB', 5, 0)

            if len(data) > 3:
                socks_init_data = struct.unpack('!BBxBIH', data)
                socks_version = socks_init_data[0]
                socks_cmd = socks_init_data[1]
                socks_atyp = socks_init_data[2]
                socks_dest_addr = socks_init_data[3]
                socks_dest_port = socks_init_data[4]

                print socket.inet_ntoa(struct.pack('!I', socks_dest_addr))
                print socks_dest_port

                socks_version = 5 # socks 5
                socks_status = 0 # Success
                socks_connection_type = 1 #IPV4
                response = struct.pack('!BBxBIH', 5, 0, 1, socks_init_data[-2], socks_init_data[-1])
                self.is_socks_complete_signal.send(self)
            client.write(response)

        else:
            self.http_parser.execute(data, len(data))
            if self.http_parser.is_headers_complete():
                print "header complete"
                self.http_header = self.http_parser.get_headers()

            if self.http_parser.is_partial_body():
                print "keep getting body"
                self.http_body.append(self.http_parser.recv_body())

            if self.http_parser.is_message_complete():
                print "message complete"
                self.http_complete = True
                print self.http_header
                print self.http_body
            

class SocksProxy(object):
    def __init__(self, ip, port):
        # pyuv instance
        self.loop = pyuv.Loop.default_loop()
        self.socks_server = pyuv.TCP(self.loop)

        # basic configurations
        self.ip = ip
        self.port = port

        # proxy
        self.clients = []
    
    def start(self):
        """
        start socks proxy server
        """
        conn_info = (self.ip, self.port)
        self.socks_server.bind(conn_info)
        self.socks_server.listen(self.on_connect)
    
    def on_connect(self, server, error):
        """
        socks connect callback
        """
        client = ProxyClient()
        server.accept(client.uv_sock)
        client.start_read()
        self.clients.append(client)


def on_signal(handle, num):
    print("program termination\n")
    loop = handle.loop
    handle.close()
    loop.stop()

loop = pyuv.Loop.default_loop()

# when user press Ctrl-C program terminated
signal_h = pyuv.Signal(loop)
signal_h.start(on_signal, signal.SIGINT)

proxy = SocksProxy("127.0.0.1", 5580)
proxy.start()

loop.run()
