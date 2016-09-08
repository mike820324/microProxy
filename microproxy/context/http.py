from collections import OrderedDict
import time


class HttpRequest(object):
    def __init__(self,
                 version="",
                 method="",
                 path="",
                 headers=None,
                 body=b"",
                 timestamp=None):
        super(HttpRequest, self).__init__()
        self.timestamp = timestamp or int(time.time() * 1000000)
        self.version = version
        self.method = method
        self.path = path
        self.body = body
        self.headers = HttpHeaders(headers)

    def serialize(self):
        json = dict(self.__dict__)
        json["body"] = self.body.encode("base64")
        json["headers"] = [h for h in self.headers]
        return json

    def __str__(self):
        return "HttpRequest(version={0}, method={1}, path={2}, headers={3})".format(
            self.version, self.method, self.path, self.headers)


class HttpResponse(object):
    def __init__(self,
                 code="",
                 reason="",
                 version="",
                 headers=None,
                 body=b"",
                 timestamp=None):
        super(HttpResponse, self).__init__()
        self.timestamp = timestamp or int(time.time() * 1000000)
        self.code = code
        self.reason = reason
        self.version = version
        self.body = body
        self.headers = HttpHeaders(headers)

    def serialize(self):
        json = dict(self.__dict__)
        json["body"] = self.body.encode("base64")
        json["headers"] = [h for h in self.headers]
        return json

    def __str__(self):
        return "HttpResponse(version={0}, code={1}, reason={2}, headers={3})".format(
            self.version, self.code, self.reason, self.headers)


class HttpHeaders(object):
    def __init__(self, headers=None):
        headers = headers or []
        if isinstance(headers, (dict, OrderedDict)):
            self.headers = headers.items()
        elif isinstance(headers, list):
            self.headers = headers
        else:
            raise ValueError("HttpHeaders not support with: " + str(type(headers)))

    def __len__(self):
        return len(self.headers)

    def __contains__(self, key):
        return key in dict(self.headers)

    def __getitem__(self, key):
        return ", ".join([v for k, v in self.headers if k == key])

    def __setitem__(self, key, value):
        self.headers.append((key, value))

    def __iter__(self):
        return self.headers.__iter__()

    def __repr__(self):
        return "HttpHeaders({0})".format(self.__dict__)

    def __str__(self):  # pragma: no cover
        return str(self.__dict__)

    def __eq__(self, other):
        return self.__dict__ == other.__dict__

    def __ne__(self, other):
        return not self.__eq__(other)
