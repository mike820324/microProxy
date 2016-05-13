from base import BaseInterceptor
from microproxy.utils import get_logger

logger = get_logger(__name__)


class LogOnlyInterceptor(BaseInterceptor):
    def request(self, request):
        logger.info("request: {0}".format(request.to_json()))

    def response(self, response):
        logger.info("response: {0}".format(response.to_json()))

    def record(self, request, response):
        logger.info("record with req: {0}, res: {1}". format(request.to_json(), response.to_json()))
