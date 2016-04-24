import unittest

from microproxy import http


class HttpTest(unittest.TestCase):

    def test_serialize(self):
        http_message = http.HttpMessage(
            version="1.1",
            status=200,
            method="GET",
            url="www.google.com",
            path="/index.html",
            query_string="query",
            header={},
            body="body")
        json = http.serialize(http_message)
        assert json["version"] == "1.1"
        assert json["status"] == 200
        assert json["method"] == "GET"
        assert json["url"] == "www.google.com"
        assert json["path"] == "/index.html"
        assert json["query_string"] == "query"
        assert json["header"] == {}
        assert json["body"] == "body".encode("base64")

    def test_deserialize(self):
        json = {}
        json["version"] = "1.1"
        json["status"] = 200
        json["method"] = "GET"
        json["url"] = "www.google.com"
        json["path"] = "/index.html"
        json["query_string"] = "query"
        json["header"] = {}
        json["body"] = "body".encode("base64")
        http_message = http.deserialize(json)
        assert http_message.version == "1.1"
        assert http_message.status == 200
        assert http_message.method == "GET"
        assert http_message.url == "www.google.com"
        assert http_message.path == "/index.html"
        assert http_message.query_string == "query"
        assert http_message.header == {}
        assert http_message.body == "body"

    def test_assemble_request(self):
        http_message = http.HttpMessage(
            version="1.1",
            status=200,
            method="GET",
            url="www.google.com",
            path="/index.html",
            query_string="query",
            header={"Transfer-Encoding": "normal"},
            body="body")
        assert http.assemble_request(http_message) == \
            b"GET www.google.com HTTP/1.1\r\n" + \
            b"Transfer-Encoding: normal\r\n\r\n" + \
            b"body"

    def test_assemble_responses_not_chunk(self):
        http_message = http.HttpMessage(
            version="1.1",
            status=200,
            method="GET",
            url="www.google.com",
            path="/index.html",
            query_string="query",
            header={"Transfer-Encoding": "normal"},
            body="body")
        response_lines = http.assemble_responses(http_message)
        assert response_lines.next() == b"HTTP/1.1 200 OK\r\n" + \
            b"Transfer-Encoding: normal\r\n\r\n" + \
            b"body"
