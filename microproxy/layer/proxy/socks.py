import struct
import ipaddress
import socket

from tornado import gen
from tornado import iostream

from base import ProxyLayer

from microproxy.utils import get_logger
from microproxy.exception import ProtocolError, SrcStreamClosedError

logger = get_logger(__name__)


class SocksLayer(ProxyLayer):
    SOCKS_VERSION = 0x05

    SOCKS_REQ_COMMAND = {
        "CONNECT": 0x1,
        "BIND": 0x02,
        "UDP_ASSOCIATE": 0x03
    }

    SOCKS_RESP_STATUS = {
        "SUCCESS": 0x0,
        "GENRAL_FAILURE": 0x01,
        "CONNECTION_NOT_ALLOWED": 0x02,
        "NETWORK_UNREACHABLE": 0x03,
        "HOST_UNREACHABLE": 0x04,
        "CONNECTION_REFUSED": 0x05,
        "TTL_EXPIRED": 0x06,
        "COMMAND_NOT_SUPPORTED": 0x07,
        "ADDRESS_TYPE_NOT_SUPPORTED": 0x08,
    }

    SOCKS_ADDR_TYPE = {
        "IPV4": 0x01,
        "DOMAINNAME": 0x03,
        "IPV6": 0x04
    }

    def __init__(self, context):
        super(SocksLayer, self).__init__(context)

    @gen.coroutine
    def process_and_return_context(self):
        yield self.socks_greeting()
        host, port, addr_type = yield self.socks_request()
        dest_stream = yield self.socks_response_with_dest_stream_creation(host, port, addr_type)

        self.context.dest_stream = dest_stream
        self.context.host = host
        self.context.port = port
        raise gen.Return(self.context)

    @gen.coroutine
    def socks_greeting(self):
        src_stream = self.context.src_stream
        data = yield src_stream.read_bytes(2)

        logger.debug("socks greeting to {0}".format(src_stream.socket.getpeername()[0]))
        socks_version, socks_nmethod = struct.unpack('BB', data)

        yield src_stream.read_bytes(socks_nmethod)

        if socks_version != self.SOCKS_VERSION:
            raise ProtocolError("not support socks version {0}".format(socks_version))

        response = struct.pack('BB', self.SOCKS_VERSION, 0)
        yield src_stream.write(response)

    @gen.coroutine
    def socks_request(self):
        src_stream = self.context.src_stream
        data = yield src_stream.read_bytes(4)

        request_header_data = struct.unpack('!BBxB', data)
        socks_version = request_header_data[0]
        socks_cmd = request_header_data[1]
        socks_atyp = request_header_data[2]

        if socks_version != self.SOCKS_VERSION:
            raise ProtocolError("not support socks version {0}".format(socks_version))

        if socks_cmd != self.SOCKS_REQ_COMMAND["CONNECT"]:
            raise ProtocolError("not support socks command {0}".format(socks_cmd))

        if socks_atyp == self.SOCKS_ADDR_TYPE["IPV4"]:
            host_data = yield src_stream.read_bytes(4)
            host = ipaddress.IPv4Address(host_data).compressed
        elif socks_atyp == self.SOCKS_ADDR_TYPE["DOMAINNAME"]:
            host_length_data = yield src_stream.read_bytes(1)
            host_length = struct.unpack("!B", host_length_data)[0]
            host_data = yield src_stream.read_bytes(host_length)
            host = host_data.decode("idna")
        elif socks_atyp == self.SOCKS_ADDR_TYPE["IPV6"]:
            host_data = yield src_stream.read_bytes(16)
            host = ipaddress.IPv6Address(host_data).compressed
        else:
            raise ProtocolError("not support socks address type")

        port_data = yield src_stream.read_bytes(2)
        port, = struct.unpack("!H", port_data)
        logger.debug("socks request to {0}:{1}".format(host, port))

        raise gen.Return((host,
                         port,
                         socks_atyp))

    @gen.coroutine
    def socks_response_with_dest_stream_creation(self, host, port, addr_type):
        src_stream = self.context.src_stream
        try:
            dest_stream = yield self.create_dest_stream((host, port))
            yield src_stream.write(struct.pack("!BBx",
                                               self.SOCKS_VERSION,
                                               self.SOCKS_RESP_STATUS["SUCCESS"]))
            if addr_type == self.SOCKS_ADDR_TYPE["IPV4"]:
                yield src_stream.write(struct.pack('!B', self.SOCKS_ADDR_TYPE["IPV4"]))
                yield src_stream.write(ipaddress.IPv4Address(host).packed)

            elif addr_type == self.SOCKS_ADDR_TYPE["IPV6"]:
                yield src_stream.write(struct.pack('!B', self.SOCKS_ADDR_TYPE["IPV6"]))
                yield src_stream.write(ipaddress.IPv6Address(host).packed)

            elif addr_type == self.SOCKS_ADDR_TYPE["DOMAINNAME"]:
                yield src_stream.write(struct.pack("!BB",
                                                   self.SOCKS_ADDR_TYPE["DOMAINNAME"],
                                                   len(host)))
                yield src_stream.write(host.encode("idna"))

            yield src_stream.write(struct.pack("!H", port))
            raise gen.Return(dest_stream)

        except gen.TimeoutError:
            logger.debug("connect to {0}:{1} timeout".format(host, port))
            yield src_stream.write(struct.pack("!BBx",
                                               self.SOCKS_VERSION,
                                               self.SOCKS_RESP_STATUS["NETWORK_UNREACHABLE"]))
        except iostream.StreamClosedError as e:
            dest_stream.close()
            raise SrcStreamClosedError(e)
