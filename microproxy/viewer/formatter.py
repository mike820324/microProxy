import logging
import re
import cssutils
import jsbeautifier
import lxml.html
import lxml.etree
import json
from pygments import highlight
from pygments.lexers import get_lexer_by_name
from pygments.formatters import Terminal256Formatter

from gviewer import Text
from gviewer.util import pygmentize

try:
    from urllib import parse as urlparse
except ImportError:
    import urlparse

from microproxy.viewer.utils import ungzip

cssutils.log.setLevel(logging.CRITICAL)


def colorize(lexer_name, raw_text):
    lexer = get_lexer_by_name(lexer_name, stripall=True)
    formatter = Terminal256Formatter()
    return highlight(raw_text, lexer, formatter)


class BaseFormatter(object):
    def match(self, headers, content_type):
        return False

    def format_body(self, body):
        raise NotImplementedError

    def format_tui(self, body):
        raise NotImplementedError

    def format_console(self, body):
        return self.format_body()


class CssFormatter(BaseFormatter):
    def match(self, headers, content_type):
        return content_type == "text/css"

    def format_body(self, body):
        sheet = cssutils.parseString(body)
        return sheet.cssText

    def format_tui(self, body):
        body = self.format_body(body)
        pygmentized_list = pygmentize(
            body, get_lexer_by_name("css"))
        return map(lambda t: Text(t), pygmentized_list)

    def format_console(self, body):
        return colorize("css", self.format_body(body))


class JsFormatter(BaseFormatter):
    def match(self, headers, content_type):
        return content_type in (
            "application/x-javascript",
            "application/javascript",
            "text/javascript"
        )

    def format_body(self, body):
        return jsbeautifier.beautify(body)

    def format_tui(self, body):
        body = self.format_body(body)
        pygmentized_list = pygmentize(
            body, get_lexer_by_name("javascript"))
        return map(lambda t: Text(t), pygmentized_list)

    def format_console(self, body):
        return colorize("javascript", self.format_body(body))


class URlEncodedFormatter(BaseFormatter):
    JSON_SUSPECT_PREFIX = ["{", "["]
    XML_SUSPECT_PREFIX = ["<"]

    def __init__(self):
        self.xml_formatter = XmlFormatter()
        self.json_formatter = JsonFormatter()

    def match(self, headers, content_type):
        return content_type in (
            "application/x-www-form-urlencoded",
        )

    def format_body(self, body):
        urlencoed_list = urlparse.parse_qsl(body)
        if not urlencoed_list:
            return ""
        max_length = max(map(lambda kv: len(kv[0]), urlencoed_list))
        texts = []
        for k, v in urlencoed_list:
            formatter = self._get_value_formatter(v)
            try:
                formatted_content = formatter.format_body(v)
            except:
                texts.append("{0}: {1}".format(
                    k.ljust(max_length), v))
            else:
                texts.append("{0}:".format(k.ljust(max_length)))
                texts.append(formatted_content)

        return u"\n".join(texts)

    def format_tui(self, body):
        urlencoed_list = urlparse.parse_qsl(body)
        if not urlencoed_list:
            return ""

        max_length = max(map(lambda kv: len(kv[0]), urlencoed_list))
        texts = []
        for k, v in urlencoed_list:
            formatter = self._get_value_formatter(v)
            try:
                formatted_list = formatter.format_tui(v)
            except:
                texts.append(Text("{0}: {1}".format(
                    k.ljust(max_length), v)))
            else:
                texts.append(Text("{0}:".format(k.ljust(max_length))))
                texts = texts + formatted_list

        return texts

    def format_console(self, body):
        urlencoed_list = urlparse.parse_qsl(body)
        if not urlencoed_list:
            return ""

        max_length = max(map(lambda kv: len(kv[0]), urlencoed_list))
        texts = []
        for k, v in urlencoed_list:
            formatter = self._get_value_formatter(v)
            try:
                formatted_content = formatter.format_console(v)
            except:
                texts.append("{0}: {1}".format(
                    k.ljust(max_length), v))
            else:
                texts.append("{0}:".format(k.ljust(max_length)))
                texts.append(formatted_content)

        return u"\n".join(texts)

    def _get_value_formatter(self, value):
        if value[0] in self.JSON_SUSPECT_PREFIX:
            return self.json_formatter
        elif value[0] in self.XML_SUSPECT_PREFIX:
            return self.xml_formatter
        else:
            return None


class HtmlFormatter(BaseFormatter):
    def __init__(self):
        self.parser = lxml.etree.HTMLParser()

    def match(self, headers, content_type):
        return content_type == "text/html"

    def format_body(self, body):
        dom = lxml.etree.fromstring(body, parser=self.parser)
        return lxml.etree.tostring(
            dom, pretty_print=True, encoding="utf-8")

    def format_tui(self, body):
        body = self.format_body(body)
        pygmentized_list = pygmentize(
            body, get_lexer_by_name("html"))
        return map(lambda t: Text(t), pygmentized_list)

    def format_console(self, body):
        return colorize("html", self.format_body(body))


class JsonFormatter(BaseFormatter):
    def match(self, headers, content_type):
        return content_type in (
            "application/json",
            "application/vnd.api+json"
        )

    def format_body(self, body):
        parsed_body = json.loads(unicode(body, "utf-8", errors="replace"))
        return json.dumps(parsed_body, indent=4)

    def format_tui(self, body):
        body = self.format_body(body)
        pygmentized_list = pygmentize(
            body, get_lexer_by_name("json"))
        return map(lambda t: Text(t), pygmentized_list)

    def format_console(self, body):
        return colorize("json", self.format_body(body))


class XmlFormatter(BaseFormatter):
    def __init__(self):
        self.parser = lxml.etree.XMLParser()

    def match(self, headers, content_type):
        return content_type in (
            "text/xml",
            "application/xml"
        )

    def format_body(self, body):
        dom = lxml.etree.fromstring(body, parser=self.parser)
        return lxml.etree.tostring(
            dom, pretty_print=True, encoding="utf-8")

    def format_tui(self, body):
        body = self.format_body(body)
        pygmentized_list = pygmentize(
            body, get_lexer_by_name("xml"))
        return map(lambda t: Text(t), pygmentized_list)

    def format_console(self, body):
        return colorize("xml", self.format_body(body))


class PlainTextFormatter(BaseFormatter):
    def match(self, headers, content_type):
        return content_type == "text/plain"

    def format_body(self, body):
        return body

    def format_tui(self, body):
        return map(lambda t: Text(t) for t in re.split(r"\r?\n", body))


class DefaultFormatter(PlainTextFormatter):
    def match(self, headers, content_type):
        return True


class Formatter(object):
    def __init__(self):
        self.formatters = [
            CssFormatter(),
            JsFormatter(),
            HtmlFormatter(),
            JsonFormatter(),
            XmlFormatter(),
            URlEncodedFormatter(),
            PlainTextFormatter(),
            DefaultFormatter()
        ]

    def format_body(self, body, headers):
        if self._is_gzip(headers):
            body = ungzip(body)

        return self.run_formatters(body, headers)

    def run_formatters(self, body, headers):
        raise NotImplementedError

    def _is_gzip(self, headers):
        for key, value in headers:
            if key.lower() == "content-encoding":
                return value == "gzip"
        return False


class TuiFormatter(Formatter):
    def run_formatters(self, body, headers):
        if "content-type" in headers:
            content_type = headers["content-type"]
        else:
            content_type = ""

        content_type = content_type.split(";")[0].strip()

        for formatter in self.formatters:
            if formatter.match(headers, content_type):
                try:
                    return formatter.format_tui(body)
                except:
                    pass
        return []


class ConsoleFormatter(Formatter):
    def run_formatters(self, body, headers):
        if "content-type" in headers:
            content_type = headers["content-type"]
        else:
            content_type = ""

        content_type = content_type.split(";")[0].strip()

        for formatter in self.formatters:
            if formatter.match(headers, content_type):
                try:
                    return formatter.format_console(body)
                except:
                    pass
        return b""
