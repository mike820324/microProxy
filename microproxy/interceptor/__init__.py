from msg_publisher import MsgPublisher
from interceptor import Interceptor

_interceptor = None


def get_interceptor(config):
    global _interceptor
    if _interceptor:
        return _interceptor

    _interceptor = Interceptor(config)
    return _interceptor
