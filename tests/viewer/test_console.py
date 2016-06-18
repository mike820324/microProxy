import unittest
from unittest import TestCase
from colored import fg, bg, attr

from microproxy.viewer.console import ColorText, TextList, StatusText, Header
from microproxy.viewer.console import Request, Response


class ColorTextTest(TestCase):
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


class TextListTest(TestCase):
    def test_default_delimiter(self):
        self.assertEqual("test\n123",
                         str(TextList([ColorText("test"), ColorText(123)])))

    def test_comma_delimiter(self):
        self.assertEqual("test,123",
                         str(TextList([ColorText("test"), ColorText(123)], delimiter=",")))

    def test_empty(self):
        self.assertEqual("", str(TextList([])))


class StatusTextTest(TestCase):
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


class HeaderTest(TestCase):
    def test_one_header(self):
        self.assertEqual(TextList([ColorText("Host: github.com", bg_color="blue")]).__dict__,
                         Header(dict(Host="github.com")).__dict__)

    def test_two_headers(self):
        self.assertEqual(TextList([ColorText("Header: Value", bg_color="blue"),
                                   ColorText("Host: github.com", bg_color="blue")]).__dict__,
                         Header(dict(Host="github.com",
                                     Header="Value")).__dict__)


class RequestTest(TestCase):
    def test_simple_request(self):
        self.assertEqual(TextList([ColorText("Request Headers:", fg_color="blue", attrs=["bold"]),
                                   Header(dict(Host="github.com"))]).__dict__,
                         Request(dict(Host="github.com")).__dict__)


class ResponseTest(TestCase):
    def test_simple_response(self):
        self.assertEqual(TextList([ColorText("Response Headers:", fg_color="blue", attrs=["bold"]),
                                   Header(dict(Host="github.com"))]).__dict__,
                         Response(dict(Host="github.com")).__dict__)


if __name__ == "__main__":
    unittest.main()
