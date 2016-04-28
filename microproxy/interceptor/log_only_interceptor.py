from base import BaseInterceptor
from microproxy.utils import get_logger
from microproxy.http import serialize

logger = get_logger(__name__)


class LogOnlyInterceptor(BaseInterceptor):
    def request(self, request):
        logger.info("request: {0}".format(serialize(request)))

    def response(self, response):
        logger.info("response: {0}".format(serialize(response)))

    def record(self, request, response):
        logger.info("record with req: {0}, res: {1}". format(serialize(request), serialize(response)))
