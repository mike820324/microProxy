from tornado import httputil
import logging
logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


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
        else:
            self.headers = headers

    def to_json(self):
        json = {}
        json["version"] = self.version
        json["method"] = self.method
        json["path"] = self.path
        json["body"] = self.body.encode("base64")
        json["headers"] = _serialize_headers(self.headers)
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
        else:
            self.headers = headers

    def append_body(self, chunk):
        self.body += bytes(chunk)

    def to_json(self):
        json = {}
        json["version"] = self.version
        json["code"] = self.code
        json["reason"] = self.reason
        json["body"] = self.body.encode("base64")
        json["headers"] = _serialize_headers(self.headers)
        return json


class HttpMessage(object):
    def __init__(self,
                 version="",
                 status="",
                 method="",
                 url="",
                 path="",
                 query_string="",
                 header=None,
                 body=b""):
        super(HttpMessage, self).__init__()
        self.version = version
        self.status = status
        self.method = method
        self.url = url
        self.path = path
        self.query_string = query_string
        if header is None:
            self.header = {}
        else:
            self.header = header
        self.body = body


def _serialize_headers(headers):
    new_headers = {}
    for (k, v) in headers.get_all():
        new_headers[k] = v
    return new_headers
