from base import BaseInterceptor
from microproxy.utils import get_logger

logger = get_logger(__name__)


class LogOnlyInterceptor(BaseInterceptor):
    def request(self, sender, **kargs):
        request = kargs["request"]
        logger.info("request: {0}".format(request.serialize()))

    def response(self, sender, **kargs):
        response = kargs["response"]
        logger.info("response: {0}".format(response.serialize()))

    def record(self, sender, **kargs):
        request = kargs["request"]
        response = kargs["response"]
        logger.info("record with req: {0}, res: {1}".format(request.serialize(), response.serialize()))
