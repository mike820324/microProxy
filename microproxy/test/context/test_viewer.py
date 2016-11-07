import unittest

from microproxy.context import ViewerContext
from microproxy.context.viewer import parse
from microproxy.version import VERSION


class TestViewerContext(unittest.TestCase):
    def test_parse(self):
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
        viewer_context = parse(data)

        self.assertIsInstance(viewer_context, ViewerContext)

        self.assertEquals("https", viewer_context.scheme)
        self.assertEquals("localhost", viewer_context.host)
        self.assertEquals(8080, viewer_context.port)
        self.assertEquals("/index", viewer_context.path)
        self.assertEquals(VERSION, viewer_context.version)

        self.assertEquals("1.1", viewer_context.request.version)
        self.assertEquals("GET", viewer_context.request.method)
        self.assertEquals("/index", viewer_context.request.path)
        self.assertEquals(1, len(viewer_context.request.headers))
        self.assertEquals("text/html",
                          viewer_context.request.headers["Content-Type"])

        self.assertEquals("1.1", viewer_context.response.version)
        self.assertEquals("200", viewer_context.response.code)
        self.assertEquals("OK", viewer_context.response.reason)
        self.assertEquals("", viewer_context.response.body)
        self.assertEquals(1, len(viewer_context.response.headers))
        self.assertEquals("text/html",
                          viewer_context.response.headers["Content-Type"])

        self.assertEquals("http/1.1", viewer_context.client_tls.alpn)
        self.assertEquals("localhost", viewer_context.client_tls.sni)
        self.assertEquals("AES", viewer_context.client_tls.cipher)

        self.assertEquals("http/1.1", viewer_context.server_tls.alpn)
        self.assertEquals("localhost", viewer_context.server_tls.sni)
        self.assertEquals("AES", viewer_context.server_tls.cipher)
