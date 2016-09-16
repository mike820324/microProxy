import StringIO
import gzip
import mock
from pygments.token import Token
import unittest

from microproxy.context import HttpHeaders
from microproxy.viewer.formatter import (
    CssFormatter, ConsoleFormatter, HtmlFormatter, JsFormatter,
    JsonFormatter, PlainTextFormatter, TuiFormatter,
    URLEncodedFormatter, XmlFormatter)


def _gzip_body(body):
    out = StringIO.StringIO()
    with gzip.GzipFile(fileobj=out, mode="w") as f:
        f.write(body)
    return out.getvalue()


class TestCssFormatter(unittest.TestCase):
    def setUp(self):
        self.formatter = CssFormatter()
        self.css_content = ".class {background: black} #id {color: red}"

    def test_match(self):
        self.assertTrue(self.formatter.match(None, "text/css"))
        self.assertFalse(self.formatter.match(None, "text/plain"))

    def test_format_body(self):
        self.assertEqual(
            self.formatter.format_body(self.css_content),
            (".class {\n"
             "    background: black\n"
             "    }\n"
             "#id {\n"
             "    color: red\n"
             "    }"))

    def test_format_tui(self):
        contents = self.formatter.format_tui(self.css_content)

        self.assertEqual(len(contents), 6)
        self.assertEqual(
            contents[0].content,
            [(Token.Name.Class, u'.class'), (Token.Text, u' '), (Token.Punctuation, u'{')])
        self.assertEqual(
            contents[1].content,
            [(Token.Name.Builtin, u'background'), (Token.Operator, u':'), (Token.Text, u' '), (Token.Name.Builtin, u'black')])
        self.assertEqual(
            contents[2].content,
            [(Token.Punctuation, u'}')])
        self.assertEqual(
            contents[3].content,
            [(Token.Name.Namespace, u'#id'), (Token.Text, u' '), (Token.Punctuation, u'{')])
        self.assertEqual(
            contents[4].content,
            [(Token.Name.Builtin, u'color'), (Token.Operator, u':'), (Token.Text, u' '), (Token.Name.Builtin, u'red')])
        self.assertEqual(
            contents[5].content,
            [(Token.Punctuation, u'}')])


class TestJsFormatter(unittest.TestCase):
    def setUp(self):
        self.formatter = JsFormatter()
        self.js_content = "var person = {firstname:\"John\",lastname:\"Doe\",age:50,eyecolor:\"blue\"};document.getElementById(\"demo\").innerHTML =person.firstname + \" is \" + person.age + \" years old.\";"

    def test_match(self):
        self.assertTrue(self.formatter.match(None, "text/javascript"))
        self.assertTrue(self.formatter.match(None, "application/javascript"))
        self.assertTrue(self.formatter.match(None, "application/x-javascript"))
        self.assertFalse(self.formatter.match(None, "text/plain"))

    def test_format_body(self):
        self.assertEqual(
            self.formatter.format_body(self.js_content),
            ("var person = {\n"
             "    firstname: \"John\",\n"
             "    lastname: \"Doe\",\n"
             "    age: 50,\n"
             "    eyecolor: \"blue\"\n"
             "};\n"
             "document.getElementById(\"demo\").innerHTML "
             "= person.firstname + \" is \" + person.age + \" years old.\";"))

    def test_format_tui(self):
        contents = self.formatter.format_tui(self.js_content)
        self.assertEqual(len(contents), 7)
        self.assertEqual(
            contents[0].content,
            [(Token.Keyword.Declaration, u'var'), (Token.Text, u' '), (Token.Name.Other, u'person'), (Token.Text, u' '), (Token.Operator, u'='), (Token.Text, u' '), (Token.Punctuation, u'{')])
        self.assertEqual(
            contents[1].content,
            [(Token.Name.Other, u'firstname'), (Token.Operator, u':'), (Token.Text, u' '), (Token.Literal.String.Double, u'"John"'), (Token.Punctuation, u',')])
        self.assertEqual(
            contents[2].content,
            [(Token.Name.Other, u'lastname'), (Token.Operator, u':'), (Token.Text, u' '), (Token.Literal.String.Double, u'"Doe"'), (Token.Punctuation, u',')])
        self.assertEqual(
            contents[3].content,
            [(Token.Name.Other, u'age'), (Token.Operator, u':'), (Token.Text, u' '), (Token.Literal.Number.Integer, u'50'), (Token.Punctuation, u',')])
        self.assertEqual(
            contents[4].content,
            [(Token.Name.Other, u'eyecolor'), (Token.Operator, u':'), (Token.Text, u' '), (Token.Literal.String.Double, u'"blue"')])
        self.assertEqual(
            contents[5].content,
            [(Token.Punctuation, u'}'), (Token.Punctuation, u';')])
        self.assertEqual(
            contents[6].content,
            [(Token.Name.Builtin, u'document'), (Token.Punctuation, u'.'), (Token.Name.Other, u'getElementById'),
             (Token.Punctuation, u'('), (Token.Literal.String.Double, u'"demo"'),
             (Token.Punctuation, u')'), (Token.Punctuation, u'.'), (Token.Name.Other, u'innerHTML'),
             (Token.Text, u' '), (Token.Operator, u'='), (Token.Text, u' '),
             (Token.Name.Other, u'person'), (Token.Punctuation, u'.'),
             (Token.Name.Other, u'firstname'), (Token.Text, u' '),
             (Token.Operator, u'+'), (Token.Text, u' '), (Token.Literal.String.Double, u'" is "'),
             (Token.Text, u' '), (Token.Operator, u'+'), (Token.Text, u' '),
             (Token.Name.Other, u'person'), (Token.Punctuation, u'.'), (Token.Name.Other, u'age'),
             (Token.Text, u' '), (Token.Operator, u'+'), (Token.Text, u' '),
             (Token.Literal.String.Double, u'" years old."'), (Token.Punctuation, u';')])


class TestHtmlFormatter(unittest.TestCase):
    def setUp(self):
        self.formatter = HtmlFormatter()
        self.html_content = (
            "<html><head><title>Hello MicroProxy</title</head>"
            "<body>Hello MicroProxy</body></html>")

    def test_match(self):
        self.assertTrue(self.formatter.match(None, "text/html"))
        self.assertFalse(self.formatter.match(None, "text/plain"))

    def test_format_body(self):
        self.assertEqual(
            self.formatter.format_body(self.html_content),
            ("<html>\n"
             "  <head>\n"
             "    <title>Hello MicroProxy</title>\n"
             "  </head>\n"
             "  <body>Hello MicroProxy</body>\n"
             "</html>\n"))

    def test_format_tui(self):
        contents = self.formatter.format_tui(self.html_content)
        self.assertEqual(len(contents), 6)
        self.assertEqual(
            contents[0].content,
            [(Token.Punctuation, u'<'), (Token.Name.Tag, u'html'), (Token.Punctuation, u'>')])
        self.assertEqual(
            contents[1].content,
            [(Token.Punctuation, u'<'), (Token.Name.Tag, u'head'), (Token.Punctuation, u'>')])
        self.assertEqual(
            contents[2].content,
            [(Token.Punctuation, u'<'), (Token.Name.Tag, u'title'), (Token.Punctuation, u'>'),
             (Token.Text, u'Hello MicroProxy'), (Token.Punctuation, u'<'), (Token.Punctuation, u'/'),
             (Token.Name.Tag, u'title'), (Token.Punctuation, u'>')])
        self.assertEqual(
            contents[3].content,
            [(Token.Punctuation, u'<'), (Token.Punctuation, u'/'), (Token.Name.Tag, u'head'), (Token.Punctuation, u'>')])
        self.assertEqual(
            contents[4].content,
            [(Token.Punctuation, u'<'), (Token.Name.Tag, u'body'), (Token.Punctuation, u'>'),
             (Token.Text, u'Hello MicroProxy'), (Token.Punctuation, u'<'), (Token.Punctuation, u'/'),
             (Token.Name.Tag, u'body'), (Token.Punctuation, u'>')])
        self.assertEqual(
            contents[5].content,
            [(Token.Punctuation, u'<'), (Token.Punctuation, u'/'), (Token.Name.Tag, u'html'), (Token.Punctuation, u'>')])


class TestJsonFormatter(unittest.TestCase):
    def setUp(self):
        self.formatter = JsonFormatter()
        self.json_content = "{\"title\":\"MicroPorxy\",\"rate\":100,\"awesome\":true}"

    def test_match(self):
        self.assertTrue(self.formatter.match(None, "application/json"))
        self.assertFalse(self.formatter.match(None, "text/plain"))

    def test_format_body(self):
        self.assertEqual(
            self.formatter.format_body(self.json_content),
            ("{\n"
             "    \"title\": \"MicroPorxy\", \n"
             "    \"rate\": 100, \n"
             "    \"awesome\": true\n"
             "}"))

    def test_format_tui(self):
        contents = self.formatter.format_tui(self.json_content)
        self.assertEqual(len(contents), 5)
        self.assertEqual(
            contents[0].content,
            [(Token.Punctuation, u'{')])
        self.assertEqual(
            contents[1].content,
            [(Token.Name.Tag, u'"title"'), (Token.Punctuation, u':'), (Token.Text, u' '),
             (Token.Literal.String.Double, u'"MicroPorxy"'), (Token.Punctuation, u',')])
        self.assertEqual(
            contents[2].content,
            [(Token.Name.Tag, u'"rate"'), (Token.Punctuation, u':'), (Token.Text, u' '),
             (Token.Literal.Number.Integer, u'100'), (Token.Punctuation, u',')])
        self.assertEqual(
            contents[3].content,
            [(Token.Name.Tag, u'"awesome"'), (Token.Punctuation, u':'), (Token.Text, u' '),
             (Token.Keyword.Constant, u'true')])
        self.assertEqual(
            contents[4].content,
            [(Token.Punctuation, u'}')])


class TestXmlFormatter(unittest.TestCase):
    def setUp(self):
        self.formatter = XmlFormatter()
        self.xml_content = "<microproxy><title>MicroProxy</title><rate>100</rate><awesome>true</awesome></microproxy>"

    def test_match(self):
        self.assertTrue(self.formatter.match(None, "text/xml"))
        self.assertTrue(self.formatter.match(None, "application/xml"))
        self.assertFalse(self.formatter.match(None, "text/plain"))

    def test_format_body(self):
        self.assertEqual(
            self.formatter.format_body(self.xml_content),
            ("<microproxy>\n"
             "  <title>MicroProxy</title>\n"
             "  <rate>100</rate>\n"
             "  <awesome>true</awesome>\n"
             "</microproxy>\n"))

    def test_format_tui(self):
        contents = self.formatter.format_tui(self.xml_content)
        self.assertEqual(len(contents), 5)
        self.assertEqual(
            contents[0].content,
            [(Token.Name.Tag, u'<microproxy'), (Token.Name.Tag, u'>')])
        self.assertEqual(
            contents[1].content,
            [(Token.Name.Tag, u'<title'), (Token.Name.Tag, u'>'), (Token.Text, u'MicroProxy'),
             (Token.Name.Tag, u'</title>')])
        self.assertEqual(
            contents[2].content,
            [(Token.Name.Tag, u'<rate'), (Token.Name.Tag, u'>'), (Token.Text, u'100'),
             (Token.Name.Tag, u'</rate>')])
        self.assertEqual(
            contents[3].content,
            [(Token.Name.Tag, u'<awesome'), (Token.Name.Tag, u'>'), (Token.Text, u'true'),
             (Token.Name.Tag, u'</awesome>')])
        self.assertEqual(
            contents[4].content,
            [(Token.Name.Tag, u'</microproxy>')])


class TestPlainTextFormatter(unittest.TestCase):
    def setUp(self):
        self.formatter = PlainTextFormatter()
        self.content = "Hello,\nthis is MicroProxy!"

    def test_match(self):
        self.assertTrue(self.formatter.match(None, "text/plain"))
        self.assertFalse(self.formatter.match(None, "text/css"))

    def test_format_body(self):
        self.assertEqual(
            self.formatter.format_body(self.content),
            "Hello,\nthis is MicroProxy!")

    def test_format_tui(self):
        contents = self.formatter.format_tui(self.content)
        self.assertEqual(len(contents), 2)
        self.assertEqual(
            contents[0].content, "Hello,")
        self.assertEqual(
            contents[1].content, "this is MicroProxy!")


class TestURLEncodedFormatter(unittest.TestCase):
    def setUp(self):
        self.formatter = URLEncodedFormatter()
        self.normal_content = "arg1=value1&arg2=100&arg3=true&longarg=this%20is%20long"
        self.complex_content = (
            "arg1=value1&"
            "jsonarg={\"key\":\"value\"}&"
            "xmlarg=<xml><text>hello</text></xml>")

    def test_match(self):
        self.assertTrue(self.formatter.match(None, "application/x-www-form-urlencoded"))
        self.assertFalse(self.formatter.match(None, "text/plain"))

    def test_format_body_normal(self):
        self.assertEqual(
            self.formatter.format_body(self.normal_content),
            ("arg1   : value1\n"
             "arg2   : 100\n"
             "arg3   : true\n"
             "longarg: this is long"))

    def test_format_tui_normal(self):
        contents = self.formatter.format_tui(self.normal_content)
        self.assertEqual(len(contents), 4)
        self.assertEqual(contents[0].content, "arg1   : value1")
        self.assertEqual(contents[1].content, "arg2   : 100")
        self.assertEqual(contents[2].content, "arg3   : true")
        self.assertEqual(contents[3].content, "longarg: this is long")

    def test_format_body_complex(self):
        self.assertEqual(
            self.formatter.format_body(self.complex_content),
            ("arg1   : value1\n"
             "jsonarg:\n"
             "{\n"
             "    \"key\": \"value\"\n"
             "}\n"
             "xmlarg :\n"
             "<xml>\n"
             "  <text>hello</text>\n"
             "</xml>\n"))

    def test_format_tui_complex(self):
        contents = self.formatter.format_tui(self.complex_content)
        self.assertEqual(len(contents), 9)
        self.assertEqual(contents[0].content, "arg1   : value1")
        self.assertEqual(contents[1].content, "jsonarg:")
        self.assertEqual(contents[2].content, [(Token.Punctuation, u'{')])
        self.assertEqual(
            contents[3].content,
            [(Token.Name.Tag, u'"key"'), (Token.Punctuation, u':'), (Token.Text, u' '),
             (Token.Literal.String.Double, u'"value"')])
        self.assertEqual(contents[4].content, [(Token.Punctuation, u'}')])
        self.assertEqual(contents[5].content, "xmlarg :")
        self.assertEqual(
            contents[6].content,
            [(Token.Name.Tag, u'<xml'), (Token.Name.Tag, u'>')])
        self.assertEqual(
            contents[7].content,
            [(Token.Name.Tag, u'<text'), (Token.Name.Tag, u'>'), (Token.Text, u'hello'),
             (Token.Name.Tag, u'</text>')])
        self.assertEqual(contents[8].content, [(Token.Name.Tag, u'</xml>')])

    def test_format_empty(self):
        self.assertEqual(
            self.formatter.format_body(""), "")
        self.assertEqual(
            self.formatter.format_tui(""), [])


class TestFormatterMixin(object):
    DEFAULT_HEADERS = HttpHeaders([
        ("content-type", "text/plain; charset=utf-8")])

    def setUp(self):
        self.mock_formatters = mock.Mock()
        self.formatters = [
            self.mock_formatters.first,
            self.mock_formatters.second]
        self.formatter = None

    def assert_called(self, formatter, *args, **kwargs):
        raise NotImplementedError

    def assert_not_called(self, formatter):
        raise NotImplementedError

    def test_match_first(self):
        self.mock_formatters.first.match = mock.Mock(
            return_value=True)
        self.mock_formatters.first.format_tui = mock.Mock(
            return_value="formatted body")
        self.mock_formatters.first.format_console = mock.Mock(
            return_value="formatted body")

        formatted_body = self.formatter.format_body("body", self.DEFAULT_HEADERS)
        self.assertEqual(formatted_body, "formatted body")

        self.mock_formatters.first.match.assert_called_with(
            self.DEFAULT_HEADERS, "text/plain")
        self.mock_formatters.second.match.assert_not_called()
        self.assert_called(self.mock_formatters.first, "body")
        self.assert_not_called(self.mock_formatters.second)

    def test_match_second(self):
        self.mock_formatters.first.match = mock.Mock(
            return_value=False)
        self.mock_formatters.second.match = mock.Mock(
            return_value=True)
        self.mock_formatters.second.format_tui = mock.Mock(
            return_value="formatted body")
        self.mock_formatters.second.format_console = mock.Mock(
            return_value="formatted body")

        formatted_body = self.formatter.format_body("body", self.DEFAULT_HEADERS)
        self.assertEqual(formatted_body, "formatted body")

        self.mock_formatters.first.match.assert_called_with(
            self.DEFAULT_HEADERS, "text/plain")
        self.mock_formatters.second.match.assert_called_with(
            self.DEFAULT_HEADERS, "text/plain")
        self.assert_not_called(self.mock_formatters.first)
        self.assert_called(self.mock_formatters.second, "body")

    def test_no_match(self):
        self.mock_formatters.first.match = mock.Mock(
            return_value=False)
        self.mock_formatters.second.match = mock.Mock(
            return_value=False)

        formatted_body = self.formatter.format_body("body", self.DEFAULT_HEADERS)
        self.assertEqual(formatted_body, self.formatter.default("body"))

        self.mock_formatters.first.match.assert_called_with(
            self.DEFAULT_HEADERS, "text/plain")
        self.mock_formatters.second.match.assert_called_with(
            self.DEFAULT_HEADERS, "text/plain")
        self.assert_not_called(self.mock_formatters.first)
        self.assert_not_called(self.mock_formatters.second)

    def test_match_but_format_format(self):
        self.mock_formatters.first.match = mock.Mock(
            return_value=True)
        self.mock_formatters.second.match = mock.Mock(
            return_value=False)
        self.mock_formatters.first.format_tui = mock.Mock(
            side_effect=ValueError)
        self.mock_formatters.first.format_console = mock.Mock(
            side_effect=ValueError)

        formatted_body = self.formatter.format_body("body", self.DEFAULT_HEADERS)
        self.assertEqual(formatted_body, self.formatter.default("body"))

        self.mock_formatters.first.match.assert_called_with(
            self.DEFAULT_HEADERS, "text/plain")
        self.mock_formatters.second.match.assert_called_with(
            self.DEFAULT_HEADERS, "text/plain")
        self.assert_called(self.mock_formatters.first, "body")
        self.assert_not_called(self.mock_formatters.second)

    def test_gzip(self):
        self.mock_formatters.first.match = mock.Mock(
            return_value=True)
        self.mock_formatters.first.format_tui = mock.Mock(
            return_value="formatted body")
        self.mock_formatters.first.format_console = mock.Mock(
            return_value="formatted body")

        headers = HttpHeaders([
            ("content-type", "text/plain"),
            ("content-encoding", "gzip")])
        formatted_body = self.formatter.format_body(
            _gzip_body("body"), headers)
        self.assertEqual(formatted_body, "formatted body")

        self.mock_formatters.first.match.assert_called_with(
            headers, "text/plain")
        self.mock_formatters.second.match.assert_not_called()
        self.assert_called(self.mock_formatters.first, "body")
        self.assert_not_called(self.mock_formatters.second)

    def test_no_content_type(self):
        self.mock_formatters.first.match = mock.Mock(
            return_value=False)
        self.mock_formatters.second.match = mock.Mock(
            return_value=False)

        empty_headers = HttpHeaders([])
        formatted_body = self.formatter.format_body("body", empty_headers)
        self.assertEqual(formatted_body, self.formatter.default("body"))

        self.mock_formatters.first.match.assert_called_with(
            empty_headers, "")
        self.mock_formatters.second.match.assert_called_with(
            empty_headers, "")
        self.assert_not_called(self.mock_formatters.first)
        self.assert_not_called(self.mock_formatters.second)


class TestTuiFormatter(TestFormatterMixin, unittest.TestCase):
    def setUp(self):
        super(TestTuiFormatter, self).setUp()
        self.formatter = TuiFormatter(self.formatters)

    def assert_called(self, formatter, *args, **kwargs):
        formatter.format_tui.assert_called_with(*args, **kwargs)

    def assert_not_called(self, formatter):
        formatter.format_tui.assert_not_called()


class TestConsoleFormatter(TestFormatterMixin, unittest.TestCase):
    def setUp(self):
        super(TestConsoleFormatter, self).setUp()
        self.formatter = ConsoleFormatter(self.formatters)

    def assert_called(self, formatter, *args, **kwargs):
        formatter.format_console.assert_called_with(*args, **kwargs)

    def assert_not_called(self, formatter):
        formatter.format_console.assert_not_called()
