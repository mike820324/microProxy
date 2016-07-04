import unittest
from tornado import httputil
from microproxy import http


class HttpTest(unittest.TestCase):

    def test_req_serialize(self):
        http_headers = httputil.HTTPHeaders()
        http_headers.parse_line("Content-Type: text/html")
        http_message = http.HttpRequest(version="1.1",
                                        method="GET",
                                        path="/hello",
                                        headers=http_headers,
                                        body="body")
        json = http_message.serialize()
        assert json["version"] == "1.1"
        assert json["method"] == "GET"
        assert json["path"] == "/hello"
        assert json["headers"] == {"Content-Type": "text/html"}
        assert json["body"] == "body".encode("base64")

    def test_resp_serialize(self):
        http_headers = httputil.HTTPHeaders()
        http_headers.parse_line("Content-Type: text/html")
        http_message = http.HttpResponse(version="1.1",
                                         code="200",
                                         reason="OK",
                                         headers=http_headers,
                                         body="body")
        json = http_message.serialize()
        assert json["version"] == "1.1"
        assert json["code"] == "200"
        assert json["reason"] == "OK"
        assert json["headers"] == {"Content-Type": "text/html"}
        assert json["body"] == "body".encode("base64")