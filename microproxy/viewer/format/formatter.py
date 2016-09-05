import re
import logging

import cssutils
import jsbeautifier
import lxml.html
import lxml.etree
import json

try:
    from urllib import parse as urlparse
except ImportError:
    import urlparse

import decompress

cssutils.log.setLevel(logging.CRITICAL)


class CssFormatter(object):
    def match(self, content_type):
        return content_type == "text/css"

    def format_body(self, body):
        sheet = cssutils.parseString(body)
        return sheet.cssText


class JsFormatter(object):
    def match(self, content_type):
        return content_type in (
            "application/x-javascript",
            "application/javascript",
            "text/javascript"
        )

    def format_body(self, body):
        return jsbeautifier.beautify(body)


class URlEncodedFormatter(object):
    JSON_SUSPECT_PREFIX = ["{", "["]
    XML_SUSPECT_PREFIX = ["<"]

    def __init__(self):
        self.xml_formatter = XmlFormatter()
        self.json_formatter = JsonFormatter()

    def match(self, content_type):
        return content_type in (
            "application/x-www-form-urlencoded",
        )

    def format_body(self, body):
        urlencoed_list = urlparse.parse_qsl(body)
        max_length = 0
        for entity in urlencoed_list:
            if len(entity[0]) > max_length:
                max_length = len(entity[0])

        pretty_string = [
            "{0}: {1}".format(key.ljust(max_length), self._try_parse_value(value))
            for key, value in
            urlencoed_list]

        return "\n".join(pretty_string)

    def _try_parse_value(self, value):
        try:
            if value[0] in self.JSON_SUSPECT_PREFIX:
                return "\n" + self.json_formatter.format_body(value)
            elif value[0] in self.XML_SUSPECT_PREFIX:
                return "\n" + self.xml_formatter.format_body(value)
            else:
                return value

        except:
            return value


class HttpFormatter(object):
    def __init__(self):
        self.parser = lxml.etree.HTMLParser()

    def match(self, content_type):
        return content_type == "text/html"

    def format_body(self, body):
        dom = lxml.etree.fromstring(body, parser=self.parser)
        return lxml.etree.tostring(
            dom, pretty_print=True, encoding="utf-8")


class JsonFormatter(object):
    def match(self, content_type):
        return content_type in (
            "application/json",
            "application/vnd.api+json"
        )

    def format_body(self, body):
        parsed_body = json.loads(unicode(body, "utf-8", errors="replace"))
        return json.dumps(parsed_body, indent=4)


class XmlFormatter(object):
    def __init__(self):
        self.parser = lxml.etree.XMLParser()

    def match(self, content_type):
        return content_type in (
            "text/xml",
            "application/xml"
        )

    def format_body(self, body):
        dom = lxml.etree.fromstring(body, parser=self.parser)
        return lxml.etree.tostring(
            dom, pretty_print=True, encoding="utf-8")


class PlainTextFormatter(object):
    def match(self, content_type):
        return content_type == "text/plain"

    def format_body(self, body):
        return body


class Formatter(object):
    def __init__(self):
        self.formatters = [
            CssFormatter(),
            JsFormatter(),
            HttpFormatter(),
            JsonFormatter(),
            XmlFormatter(),
            URlEncodedFormatter(),
            PlainTextFormatter()
        ]

    def format_request(self, request):
        headers_dict = dict(request["headers"])
        body = request["body"].decode("base64")

        if self._is_gzip(headers_dict):
            body = decompress.ungzip(body)

        body = self.format_body(headers_dict, body)

        return self._process_final_body(body)

    def format_response(self, response):
        headers_dict = dict(response["headers"])
        body = response["body"].decode("base64")

        if self._is_gzip(headers_dict):
            body = decompress.ungzip(body)

        body = self.format_body(headers_dict, body)

        return self._process_final_body(body)

    def format_body(self, headers, body):
        if "Content-Type" in headers.keys():
            content_type = headers["Content-Type"]
        elif "content-type" in headers.keys():
            content_type = headers["content-type"]
        else:
            # NOTE: cannot figure out content type
            # return body directly
            return ""

        content_type = content_type.split(";")[0].strip()

        for formatter in self.formatters:
            if formatter.match(content_type):
                try:
                    return formatter.format_body(body)
                except:
                    return body
        return ""

    def _process_final_body(self, body):
        body = self._tab_to_space(body)
        return re.split("\r?\n", body)

    def _tab_to_space(self, body):
        return body.replace("\t", "    ")

    def _is_gzip(self, headers):
        if "Content-Encoding" in headers.keys():
            return headers["Content-Encoding"] == "gzip"
        if "content-encoding" in headers.keys():
            return headers["content-encoding"] == "gzip"
        return False
