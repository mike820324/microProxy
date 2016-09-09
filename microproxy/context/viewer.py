from http import HttpRequest, HttpResponse


class ViewerContext(object):
    """
    ViewerContext: Context used to communicate with viewer.
    """
    def __init__(self,
                 scheme="",
                 host="",
                 port=0,
                 path="",
                 request=None,
                 response=None):

        super(ViewerContext, self).__init__()
        self.scheme = scheme
        self.host = host
        self.port = port
        self.path = path

        if isinstance(request, dict):
            self.request = HttpRequest(**request)
        elif isinstance(request, HttpRequest):
            self.request = request
        elif request:
            raise ValueError("not support request type: {0}".format(
                type(request)))
        else:
            self.request = None

        if isinstance(response, dict):
            self.response = HttpResponse(**response)
        elif isinstance(response, HttpResponse):
            self.response = response
        elif response:
            raise ValueError("not support response type: {0}".format(
                type(response)))
        else:
            self.response = None

    def serialize(self):
        json = dict(self.__dict__)
        if self.request:
            json["request"] = self.request.serialize()
        if self.response:
            json["response"] = self.response.serialize()
        return json
