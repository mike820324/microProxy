from collections import OrderedDict
import time

from base import Serializable


class HttpRequest(Serializable):
    def __init__(self,
                 version="",
                 method="",
                 path="",
                 headers=None,
                 body=b"",
                 timestamp=None,
                 **kwargs):
        super(HttpRequest, self).__init__()
        self.timestamp = timestamp or int(time.time() * 1000000)
        self.version = version
        self.method = method
        self.path = path
        self.body = body
        self.headers = HttpHeaders(headers)

    def serialize(self):
        data = super(HttpRequest, self).serialize()
        data["body"] = self.body.encode("base64")
        return data

    @classmethod
    def deserialize(cls, data):
        if isinstance(data, cls):
            return data

        req = super(HttpRequest, cls).deserialize(data)
        if req and req.body:
            req.body = req.body.decode("base64")
        return req

    def __str__(self):
        display_data = {
            "version": self.version,
            "method": self.method,
            "path": self.path,
            "headers": self.headers
        }
        return "{0}{1}".format(type(self).__name__, display_data)


class HttpResponse(Serializable):
    def __init__(self,
                 code="",
                 reason="",
                 version="",
                 headers=None,
                 body=b"",
                 timestamp=None,
                 **kwargs):
        super(HttpResponse, self).__init__()
        self.timestamp = timestamp or int(time.time() * 1000000)
        self.code = code
        self.reason = reason
        self.version = version
        self.body = body
        self.headers = HttpHeaders(headers)

    def serialize(self):
        data = super(HttpResponse, self).serialize()
        data["body"] = self.body.encode("base64")
        return data

    @classmethod
    def deserialize(cls, data):
        if isinstance(data, cls):
            return data

        resp = super(HttpResponse, cls).deserialize(data)
        if resp and resp.body:
            resp.body = resp.body.decode("base64")
        return resp

    def __str__(self):
        display_data = {
            "version": self.version,
            "code": self.code,
            "reason": self.reason,
            "headers": self.headers
        }
        return "{0}{1}".format(type(self).__name__, display_data)


class HttpHeaders(Serializable):
    def __init__(self, headers=None):
        headers = headers or []
        if isinstance(headers, (dict, OrderedDict)):
            self.headers = headers.items()
        elif isinstance(headers, list):
            self.headers = headers
        elif isinstance(headers, HttpHeaders):
            self.headers = list(headers.headers)
        elif not headers:
            self.headers = []
        else:
            raise ValueError("HttpHeaders not support with: " + str(type(headers)))

    def __len__(self):
        return len(self.headers)

    def __contains__(self, key):
        for k, _ in self.headers:
            if k.lower() == key.lower():
                return True
        return False

    def __getitem__(self, key):
        return ", ".join([v for k, v in self.headers if k.lower() == key.lower()])

    def __setitem__(self, key, value):
        self.headers.append((key, value))

    def __iter__(self):
        return self.headers.__iter__()

    def __eq__(self, other):
        return self.__dict__ == other.__dict__

    def __ne__(self, other):
        return not self.__eq__(other)

    def serialize(self):
        return [h for h in self.headers]
