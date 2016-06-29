from tornado import httputil


class HttpRequest(object):
    def __init__(self,
                 version="",
                 method="",
                 path="",
                 headers=None,
                 body=b""):
        super(HttpRequest, self).__init__()
        self.version = version
        self.method = method
        self.path = path
        self.body = body
        if headers is None:
            self.headers = httputil.HTTPHeaders()
        elif isinstance(headers, httputil.HTTPHeaders):
            self.headers = headers
        else:
            self.headers = httputil.HTTPHeaders(headers)

    def serialize(self):
        json = {}
        json["version"] = self.version
        json["method"] = self.method
        json["path"] = self.path
        json["body"] = self.body.encode("base64")
        json["headers"] = {k: v for k, v in self.headers.get_all()}
        return json


class HttpResponse(object):
    def __init__(self,
                 code="",
                 reason="",
                 version="",
                 headers=None,
                 body=b""):
        super(HttpResponse, self).__init__()
        self.code = code
        self.reason = reason
        self.version = version
        self.body = body
        if headers is None:
            self.headers = httputil.HTTPHeaders()
        elif isinstance(headers, httputil.HTTPHeaders):
            self.headers = headers
        else:
            self.headers = httputil.HTTPHeaders(headers)

    def serialize(self):
        json = {}
        json["version"] = self.version
        json["code"] = self.code
        json["reason"] = self.reason
        json["body"] = self.body.encode("base64")
        json["headers"] = {k: v for k, v in self.headers.get_all()}
        return json
