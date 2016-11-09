import unittest
from microproxy.context import HttpRequest, HttpResponse, HttpHeaders


class TestHttp(unittest.TestCase):
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

    def test_req_deserialize(self):
        request = HttpRequest.deserialize({
            "version": "1.1",
            "method": "GET",
            "path": "/hello",
            "headers": [("Content-Type", "text/html")],
            "body": "body".encode("base64")
        })
        self.assertEqual(request.version, "1.1")
        self.assertEqual(request.method, "GET")
        self.assertEqual(request.path, "/hello")
        self.assertEqual(request.headers, HttpHeaders([("Content-Type", "text/html")]))
        self.assertEqual(request.body, "body")

    def test_resp_deserialize(self):
        response = HttpResponse.deserialize({
            "version": "1.1",
            "code": "200",
            "reason": "OK",
            "headers": [("Content-Type", "text/html")],
            "body": "body".encode("base64")
        })
        self.assertEqual(response.version, "1.1")
        self.assertEqual(response.code, "200")
        self.assertEqual(response.reason, "OK")
        self.assertEqual(response.headers, HttpHeaders([("Content-Type", "text/html")]))
        self.assertEqual(response.body, "body")


class TestHttpHeaders(unittest.TestCase):
    def setUp(self):
        self.headers = HttpHeaders([
            ("Host", "localhost"),
            ("Accept", "application/xml"),
            ("Yayaya", "Yoyoyo")])

    def test_same_order_iteration(self):
        headers = [h for h in self.headers]
        self.assertEqual(
            headers,
            [("Host", "localhost"),
             ("Accept", "application/xml"),
             ("Yayaya", "Yoyoyo")])

    def test_contains(self):
        self.assertTrue("Host" in self.headers)
        self.assertFalse("Hahaha" in self.headers)

    def test_getitem(self):
        self.assertEqual(self.headers["Host"], "localhost")

    def test_setitem(self):
        self.headers["hahaha"] = "hey!!!"
        self.assertEqual(len(self.headers), 4)
        self.assertEqual(self.headers["hahaha"], "hey!!!")

    def test_eq(self):
        self.assertEqual(
            self.headers,
            HttpHeaders([
                ("Host", "localhost"),
                ("Accept", "application/xml"),
                ("Yayaya", "Yoyoyo")]))

    def test_neq(self):
        self.assertNotEqual(
            self.headers,
            HttpHeaders([]))

    def test_construct_with_dict(self):
        headers = HttpHeaders(dict(
            Host="localhost", Accept="application/xml",
            Yayaya="Yoyoyo"))
        self.assertEqual(len(headers), 3)
        self.assertEqual(headers["Host"], "localhost")
        self.assertEqual(headers["Accept"], "application/xml")
        self.assertEqual(headers["Yayaya"], "Yoyoyo")

    def test_construct_failed(self):
        with self.assertRaises(ValueError):
            HttpHeaders("aaa")

if __name__ == "__main__":
    unittest.main()
