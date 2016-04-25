from http_parser.parser import HttpParser
from http_parser.util import status_reasons
import logging
logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class HttpMessage(object):
    def __init__(self,
                 version="",
                 status="",
                 method="",
                 url="",
                 path="",
                 query_string="",
                 header=[],
                 body=b""):
        super(HttpMessage, self).__init__()
        self.version = version
        self.status = status
        self.method = method
        self.url = url
        self.path = path
        self.query_string = query_string
        self.header = header
        self.body = body


class HttpMessageBuilder(object):
    def __init__(self):
        super(HttpMessageBuilder, self).__init__()
        self.http_parser = HttpParser()

    def parse(self, data):
        self.http_parser.execute(data, len(data))

    @property
    def is_done(self):
        return self.http_parser.is_message_complete()

    def build(self):
        if not self.is_done:
            raise IOError
        version = "{0}.{1}".format(*self.http_parser.get_version())
        status = int(self.http_parser.get_status_code())
        method = self.http_parser.get_method()
        url = self.http_parser.get_url()
        path = self.http_parser.get_path()
        query_string = self.http_parser.get_query_string()
        header = self.http_parser.get_headers()
        body = self.http_parser.recv_body()
        return HttpMessage(version=version,
                           status=status,
                           method=method,
                           url=url,
                           path=path,
                           query_string=query_string,
                           header=header,
                           body=body)


def serialize(http_message):
    data = {}
    data["version"] = http_message.version
    data["status"] = http_message.status
    data["method"] = http_message.method
    data["url"] = http_message.url
    data["path"] = http_message.path
    data["query_string"] = http_message.query_string
    data["header"] = http_message.header
    data["body"] = http_message.body.encode("base64")
    return data


def deserialize(data):
    version = data["version"]
    status = data["status"]
    method = data["method"]
    url = data["url"]
    path = data["path"]
    query_string = data["query_string"]
    header = data["header"]
    body = data["body"].decode("base64")

    return HttpMessage(version=version,
                       status=status,
                       method=method,
                       url=url,
                       path=path,
                       query_string=query_string,
                       header=header,
                       body=body)


def _assemble_req_header(http_message):
    http_header_query_str = "{0} {1} HTTP/{2}".format(http_message.method,
                                                      http_message.url,
                                                      http_message.version)

    http_header_fields = ["{0}: {1}".format(key, http_message.header[key]) for key in http_message.header]

    http_header_list = [http_header_query_str]
    http_header_list.extend(http_header_fields)

    return "{0}\r\n\r\n".format("\r\n".join(http_header_list))


def assemble_request(http_message):
    final_data = b"{0}{1}".format(_assemble_req_header(http_message),
                                  http_message.body)
    return final_data


def is_chunked_encoding(http_message):
    try:
        return "chunked" in http_message.header['Transfer-Encoding'].lower()
    except KeyError:
        return False


def _assemble_res_header(http_message):
    http_header_query_str = "HTTP/{0} {1} {2}".format(http_message.version,
                                                      http_message.status,
                                                      status_reasons[http_message.status])

    http_header_fields = []
    for header_key in http_message.header:
        try:
            header_value = bytes(http_message.header[header_key])
        except UnicodeEncodeError:
            header_value = bytes(http_message.header[header_key].encode("utf8"))
            logger.info("Unicode Encode Error in : {0}".format(header_key))
        finally:
            http_header_fields.append(b"{0}: {1}".format(header_key, header_value))

    http_header_list = [http_header_query_str]
    http_header_list.extend(http_header_fields)

    return "{0}\r\n\r\n".format("\r\n".join(http_header_list))


def assemble_responses(http_message):
    if is_chunked_encoding(http_message):
        chunk_size = 1024
        chunks = [http_message.body[i:i + chunk_size] for i in range(0, len(http_message.body), chunk_size)]
        if not chunks:
            yield b"{0}".format(_assemble_res_header(http_message))
        else:
            yield b"{0}{1:x}\r\n{2}\r\n".format(_assemble_res_header(http_message),
                                                len(chunks[0]),
                                                chunks.pop(0))
            for chunk in chunks:
                yield b"{0:x}\r\n{1}\r\n".format(len(chunk), chunk)

        yield b"0\r\n\r\n"

    else:
        yield b"{0}{1}".format(_assemble_res_header(http_message),
                               http_message.body)
