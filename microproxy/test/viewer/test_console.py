import unittest
from unittest import TestCase
from colored import fg, bg, attr

from microproxy.viewer.console import (
    ColorText, TextList, StatusText, Header,
    Request, Response, construct_status_summary,
    construct_color_msg)
from microproxy.context import (
    ViewerContext, HttpRequest, HttpResponse)


class TestColorText(TestCase):
    def test_clear_text(self):
        self.assertEqual("clear text", str(ColorText("clear text")))

    def test_fg(self):
        self.assertEqual(fg("blue") + "fg test" + attr("reset"),
                         str(ColorText("fg test", fg_color="blue")))

    def test_bg(self):
        self.assertEqual(bg("blue") + "bg test" + attr("reset"),
                         str(ColorText("bg test", bg_color="blue")))

    def test_bold(self):
        self.assertEqual(attr("bold") + "bold test" + attr("reset"),
                         str(ColorText("bold test", attrs=["bold"])))

    def test_bold_and_underlined(self):
        self.assertEqual(attr("bold") + attr("underlined") + "bold underlined test" + attr("reset"),
                         str(ColorText("bold underlined test", attrs=["bold", "underlined"])))

    def test_fg_and_bg(self):
        self.assertEqual(fg("blue") + bg("blue") + "fg bg test" + attr("reset"),
                         str(ColorText("fg bg test", fg_color="blue", bg_color="blue")))

    def test_fg_and_bg_and_bold(self):
        self.assertEqual(fg("blue") + bg("blue") + attr("bold") + "fg bg test" + attr("reset"),
                         str(ColorText("fg bg test", fg_color="blue", bg_color="blue", attrs=["bold"])))


class TestTextList(TestCase):
    def test_default_delimiter(self):
        self.assertEqual("test\n123",
                         str(TextList([ColorText("test"), ColorText(123)])))

    def test_comma_delimiter(self):
        self.assertEqual("test,123",
                         str(TextList([ColorText("test"), ColorText(123)], delimiter=",")))

    def test_empty(self):
        self.assertEqual("", str(TextList([])))


class TestStatusText(TestCase):
    def test_status_ok(self):
        self.assertEqual(TextList([ColorText(200, fg_color="green", attrs=["bold"]),
                                   "GET", "http://github.com/index"],
                                  delimiter=" ").__dict__,
                         StatusText(200, "GET", "http://github.com", "/index").__dict__)

    def test_status_error(self):
        self.assertEqual(TextList([ColorText(400, fg_color="red", attrs=["bold"]),
                                   "GET", "http://github.com/index"],
                                  delimiter=" ").__dict__,
                         StatusText(400, "GET", "http://github.com", "/index").__dict__)


class TestHeader(TestCase):
    def test_one_header(self):
        expected = TextList([ColorText("Host: github.com", bg_color="blue")])
        self.assertEqual(
            expected.__dict__,
            Header([("Host", "github.com")]).__dict__)

    def test_two_headers(self):
        expected = TextList(
            [ColorText("Header: Value", bg_color="blue"),
             ColorText("Host: github.com", bg_color="blue")])
        self.assertEqual(
            expected.__dict__,
            Header([("Header", "Value"), ("Host", "github.com")]).__dict__)


class TestRequest(TestCase):
    def test_simple_request(self):
        request = HttpRequest(headers=[("Host", "github.com")])
        expected = TextList(
            [ColorText("Request Headers:", fg_color="blue", attrs=["bold"]),
             Header([("Host", "github.com")])])
        self.assertEqual(
            expected.__dict__,
            Request(request).__dict__)


class TestResponse(TestCase):
    def test_simple_response(self):
        response = HttpResponse(headers=[("Content-Type", "application/xml")])
        expected = TextList(
            [ColorText("Response Headers:", fg_color="blue", attrs=["bold"]),
             Header([("Content-Type", "application/xml")])])
        self.assertEqual(
            expected.__dict__,
            Response(response).__dict__)


class TestConsole(TestCase):
    def test_construct_status_summary(self):
        status = construct_status_summary(
            ViewerContext.deserialize({
                "host": "example.com",
                "path": "/index",
                "response": {
                    "code": 200,
                },
                "request": {
                    "method": "GET",
                },
            }))
        self.assertEqual(status, StatusText(200, "GET", "example.com", "/index"))

    def test_construct_color_msg_with_status(self):
        msg = construct_color_msg(
            ViewerContext.deserialize({
                "host": "example.com",
                "path": "/index",
                "response": {
                    "code": 200,
                },
                "request": {
                    "method": "GET",
                },
            }), "status")
        self.assertEqual(msg, StatusText(200, "GET", "example.com", "/index"))

    def test_construct_color_msg_with_header(self):
        msg = construct_color_msg(ViewerContext.deserialize({
            "host": "example.com",
            "path": "/index",
            "response": {
                "code": 200,
                "headers": [
                    ("Content-Type", "application/xml"),
                ],
                "body": "response".encode("base64"),
            },
            "request": {
                "method": "GET",
                "headers": [
                    ("Content-Type", "application/xml"),
                ],
            },
        }), "header")

        self.assertEqual(
            msg,
            TextList([
                StatusText(200, "GET", "example.com", "/index"),
                Request(HttpRequest(method="GET", headers=[("Content-Type", "application/xml")])),
                Response(HttpResponse(code=200, headers=[("Content-Type", "application/xml")]))
            ])
        )

    def test_construct_color_msg_with_body(self):
        msg = construct_color_msg(ViewerContext.deserialize({
            "host": "example.com",
            "path": "/index",
            "response": {
                "code": 200,
                "headers": [
                    ("Content-Type", "application/xml"),
                ],
                "body": "<xml>Response</xml>".encode("base64"),
            },
            "request": {
                "method": "GET",
                "headers": [
                    ("Content-Type", "application/xml"),
                ],
                "body": "<xml>Request</xml>".encode("base64"),
            },
        }), "body")

        self.assertEqual(
            msg,
            TextList([
                StatusText(200, "GET", "example.com", "/index"),
                Request(HttpRequest(
                    method="GET",
                    headers=[("Content-Type", "application/xml")],
                    body="<xml>Request</xml>"), show_body=True),
                Response(HttpResponse(
                    code=200,
                    headers=[("Content-Type", "application/xml")],
                    body="<xml>Response</xml>"), show_body=True)
            ])
        )


if __name__ == "__main__":
    unittest.main()
