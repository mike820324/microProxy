import unittest

from microproxy.context import ViewerContext
from microproxy.version import VERSION


class TestViewerContext(unittest.TestCase):
    def test_deserialize(self):
        data = {
            "scheme": "https",
            "host": "localhost",
            "port": 8080,
            "path": "/index",
            "request": {
                "version": "1.1",
                "method": "GET",
                "path": "/index",
                "headers": [["Content-Type", "text/html"]],
            },
            "response": {
                "version": "1.1",
                "code": "200",
                "reason": "OK",
                "headers": [["Content-Type", "text/html"]],
                "body": "",
            },
            "client_tls": {
                "sni": "localhost",
                "alpn": "http/1.1",
                "cipher": "AES",
            },
            "server_tls": {
                "sni": "localhost",
                "alpn": "http/1.1",
                "cipher": "AES",
            },
        }
        viewer_context = ViewerContext.deserialize(data)

        self.assertIsInstance(viewer_context, ViewerContext)

        self.assertEqual("https", viewer_context.scheme)
        self.assertEqual("localhost", viewer_context.host)
        self.assertEqual(8080, viewer_context.port)
        self.assertEqual("/index", viewer_context.path)
        self.assertEqual(VERSION, viewer_context.version)

        self.assertEqual("1.1", viewer_context.request.version)
        self.assertEqual("GET", viewer_context.request.method)
        self.assertEqual("/index", viewer_context.request.path)
        self.assertEqual(1, len(viewer_context.request.headers))
        self.assertEqual("text/html",
                         viewer_context.request.headers["Content-Type"])

        self.assertEqual("1.1", viewer_context.response.version)
        self.assertEqual("200", viewer_context.response.code)
        self.assertEqual("OK", viewer_context.response.reason)
        self.assertEqual("", viewer_context.response.body)
        self.assertEqual(1, len(viewer_context.response.headers))
        self.assertEqual("text/html",
                         viewer_context.response.headers["Content-Type"])

        self.assertEqual("http/1.1", viewer_context.client_tls.alpn)
        self.assertEqual("localhost", viewer_context.client_tls.sni)
        self.assertEqual("AES", viewer_context.client_tls.cipher)

        self.assertEqual("http/1.1", viewer_context.server_tls.alpn)
        self.assertEqual("localhost", viewer_context.server_tls.sni)
        self.assertEqual("AES", viewer_context.server_tls.cipher)
