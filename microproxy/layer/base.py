from copy import copy
from datetime import timedelta
import socket
from tornado import gen

from microproxy.tornado_ext.iostream import MicroProxyIOStream


class Layer(object):
    def process_and_return_context(self):
        raise NotImplementedError


class ApplicationLayer(Layer):
    def __init__(self, server_state, context):
        super(ApplicationLayer, self).__init__()
        self.context = copy(context)
        self.server_state = server_state

    @property
    def interceptor(self):
        return self.server_state.interceptor

    @property
    def config(self):
        return self.server_state.config

    @property
    def src_stream(self):
        return self.context.src_stream

    @src_stream.setter
    def src_stream(self, value):
        self.context.src_stream = value

    @property
    def dest_stream(self):
        return self.context.dest_stream

    @dest_stream.setter
    def dest_stream(self, value):
        self.context.dest_stream = value

    def __repr__(self):
        return "{0}({1} -> {2}:{3})".format(
            type(self).__name__, self.context.src_info,
            self.context.host, self.context.port)

    def __str__(self):
        return "{0}({1} -> {2}:{3})".format(
            type(self).__name__, self.context.src_info,
            self.context.host, self.context.port)


class DestStreamCreatorMixin:
    @gen.coroutine
    def create_dest_stream(self, dest_addr_info):
        dest_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
        dest_stream = MicroProxyIOStream(dest_socket)
        yield gen.with_timeout(
            timedelta(seconds=5), dest_stream.connect(dest_addr_info))
        raise gen.Return(dest_stream)


class ProxyLayer(Layer, DestStreamCreatorMixin):
    def __init__(self, context, **kwargs):
        super(ProxyLayer, self).__init__()
        self.context = copy(context)

        for k, v in kwargs.iteritems():
            self.__setattr__(k, v)

    def __repr__(self):
        return "{0}({1})".format(
            type(self).__name__, self.context.src_info)

    def __str__(self):
        return "{0}({1}) ".format(
            type(self).__name__, self.context.src_info)
