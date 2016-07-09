import unittest
from microproxy.context import HttpRequest, HttpResponse


class HttpTest(unittest.TestCase):

    def test_req_serialize(self):
        http_message = HttpRequest(version="1.1",
                                   method="GET",
                                   path="/hello",
                                   headers=[("Content-Type", "text/html")],
                                   body="body")
        json = http_message.serialize()
        self.assertEqual(json["version"], "1.1")
        self.assertEqual(json["method"], "GET")
        self.assertEqual(json["path"], "/hello")
        self.assertEqual(json["headers"], [("Content-Type", "text/html")])
        self.assertEqual(json["body"], "body".encode("base64"))

    def test_resp_serialize(self):
        http_message = HttpResponse(version="1.1",
                                    code="200",
                                    reason="OK",
                                    headers=[("Content-Type", "text/html")],
                                    body="body")
        json = http_message.serialize()
        self.assertEqual(json["version"], "1.1")
        self.assertEqual(json["code"], "200")
        self.assertEqual(json["reason"], "OK")
        self.assertEqual(json["headers"], [("Content-Type", "text/html")])
        self.assertEqual(json["body"], "body".encode("base64"))
