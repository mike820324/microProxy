"""This module contains two helper function to initialize and get the server state."""

from microproxy.context import ServerContext
from microproxy.interceptor import Interceptor
from microproxy.interceptor import MsgPublisher
from microproxy.interceptor import PluginManager
from microproxy.cert import CertStore


def _init_cert_store(config):
    return CertStore(config)


def _init_interceptor(config, publish_socket):
    plugin_manager = PluginManager(config)
    msg_publisher = MsgPublisher(config, zmq_socket=publish_socket)
    return Interceptor(
        plugin_manager=plugin_manager, msg_publisher=msg_publisher)


def init_server_state(config, publish_socket):
    """Initialize the ServerContext by config.

    Args:
        config (dict): The config object pass by user.
        publish_socket (object): The zmq pub socket for interceptor

    Returns:
        object: ServerContext.
    """
    cert_store = _init_cert_store(config)
    interceptor = _init_interceptor(config, publish_socket)

    return ServerContext(
        config=config, interceptor=interceptor, cert_store=cert_store)
