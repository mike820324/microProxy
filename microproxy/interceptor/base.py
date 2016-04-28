class BaseInterceptor(object):
    def request(self, request):
        raise NotImplementedError

    def response(self, response):
        raise NotImplementedError

    def record(self, request, response):
        raise NotImplementedError
