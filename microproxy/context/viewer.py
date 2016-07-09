
class ViewerContext(object):
    """
    ViewerContext: Context used to communicate with viewer.
    """
    def __init__(self,
                 scheme,
                 host,
                 port,
                 path,
                 request,
                 response):

        super(ViewerContext, self).__init__()
        self.scheme = scheme
        self.host = host
        self.port = port
        self.path = path
        self.request = request
        self.response = response

    def serialize(self):
        json = {}
        json["scheme"] = self.scheme
        json["host"] = self.host
        json["port"] = self.port
        json["path"] = self.path
        json["request"] = self.request.serialize()
        json["response"] = self.response.serialize()
        return json
