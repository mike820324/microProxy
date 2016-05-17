import struct
import socket

from tornado import gen
from tornado import iostream

import base
from microproxy.utils import get_logger

logger = get_logger(__name__)


class SocksProxyHandler(base.ProxyHandler):
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

    def __init__(self):
        super(SocksProxyHandler, self).__init__()

    @gen.coroutine
    def read_and_return_addr(self, src_stream):
        try:
            data = yield src_stream.read_bytes(3)
            yield self.socks_greeting(src_stream, data)
            data = yield src_stream.read_bytes(4)
            dest_addr_info = yield self.socks_request(src_stream, data)
            raise gen.Return(dest_addr_info)
        except iostream.StreamClosedError:
            logger.warning("Source Stream Closed")

    @gen.coroutine
    def socks_greeting(self, src_stream, data):
        logger.debug("socks greeting to {0}".format(src_stream.socket.getpeername()[0]))
        socks_init_data = struct.unpack('BBB', data)
        socks_version = socks_init_data[0]
        socks_nmethod = socks_init_data[1]

        if socks_version != self.SOCKS_VERSION:
            logger.warning("Socks Version incorrent : {}".format(socks_version))
            # fixme: response with error
            src_stream.close()

        if socks_nmethod != 1:
            logger.warning("SOCKS5 Auth not supported")
            # fixme: response with error
            src_stream.close()
        else:
            response = struct.pack('BB', self.SOCKS_VERSION, 0)
            yield src_stream.write(response)

    @gen.coroutine
    def socks_request(self, src_stream, data):
        request_header_data = struct.unpack('!BBxB', data)
        socks_version = request_header_data[0]
        socks_cmd = request_header_data[1]
        socks_atyp = request_header_data[2]

        if socks_version != self.SOCKS_VERSION:
            logger.warning("Socks Version incorrent : {}".format(socks_version))
            # fixme: response with error
            src_stream.close()

        if socks_cmd != self.SOCKS_REQ_COMMAND["CONNECT"]:
            logger.warning("Socks Command Not Supported : {}".format(socks_cmd))
            # fixme: response with error
            src_stream.close()

        if socks_atyp == self.SOCKS_ADDR_TYPE["IPV6"]:
            logger.warning("Socks Address Type Not Supported : {}".format(socks_atyp))
            # fixme: response with error
            src_stream.close()

        elif socks_atyp == self.SOCKS_ADDR_TYPE["IPV4"]:
            data = yield src_stream.read_bytes(6)
            request_info = struct.unpack("!IH", data)
            dest_addr_info = (socket.inet_ntoa(struct.pack('!I', request_info[0])),
                              request_info[1])
            response = struct.pack('!BBxBIH',
                                   self.SOCKS_VERSION,
                                   self.SOCKS_RESP_STATUS["SUCCESS"],
                                   self.SOCKS_ADDR_TYPE["IPV4"],
                                   *request_info)

        elif socks_atyp == self.SOCKS_ADDR_TYPE["DOMAINNAME"]:
            data = yield src_stream.read_bytes(1)
            host_length = struct.unpack("!B", data)[0]

            data = yield src_stream.read_bytes(host_length + 2)
            dest_addr_info = struct.unpack("!{0}sH".format(host_length), data)
            response = struct.pack("!BBxBB{0}sH".format(host_length),
                                   self.SOCKS_VERSION,
                                   self.SOCKS_RESP_STATUS["SUCCESS"],
                                   self.SOCKS_ADDR_TYPE["DOMAINNAME"],
                                   host_length,
                                   *dest_addr_info)

        logger.debug("socks request to {0}:{1}".format(*dest_addr_info))
        yield src_stream.write(response)
        raise gen.Return(dest_addr_info)
