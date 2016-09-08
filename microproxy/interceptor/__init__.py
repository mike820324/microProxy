from msg_publisher import MsgPublisher
from interceptor import Interceptor

_interceptor = None


def init_interceptor(config, msg_publisher=None):
    global _interceptor
    if _interceptor:
        raise ValueError
    _interceptor = Interceptor(config, msg_publisher=msg_publisher)


def get_interceptor():
    global _interceptor
    if not _interceptor:
        raise ValueError
    return _interceptor
