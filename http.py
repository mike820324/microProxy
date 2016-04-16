from http_parser.parser import HttpParser
from status_codes import RESPONSES

class HttpMessage(object):
    def __init__(self):
        super(HttpMessage, self).__init__()
        self.parser = HttpParser()
        self.version = ""
        self.status = ""
        self.method = ""
        self.url = ""
        self.path = ""
        self.query_string = ""
        self.header = None
        self.body = None
    
    def data(self):
        raise NotImplementedError

    @property
    def is_done(self):
        return self.parser.is_message_complete()

    def clear(self):
        self.parser = HttpParser()

    def parse(self, data):
        self.parser.execute(data, len(data))

        if self.parser.is_message_complete():
            self.version = "{0}.{1}".format(self.parser.get_version()[0], self.parser.get_version()[1])
            self.status = self.parser.get_status_code()
            self.method = self.parser.get_method()
            self.url = self.parser.get_url()
            self.path = self.parser.get_path()
            self.query_string = self.parser.get_query_string()
            self.header = self.parser.get_headers()
            self.body = self.parser.recv_body()

class HttpRequest(HttpMessage):
    def __init__(self):
        super(HttpRequest, self).__init__()
    
    def _assemble_header(self):
        http_header_query_str = "{0} {1} HTTP/{2}".format(self.method, self.url, self.version)
        http_header_fields = [ "{0}: {1}".format(key, self.header[key]) for key in self.header ]

        http_header_list = [http_header_query_str]
        http_header_list.extend(http_header_fields)

        return "{0}\r\n\r\n".format("\r\n".join(http_header_list))

    def _assemble_body(self):
        raise NotImplementedError

    def _assemble_data(self):
        raise NotImplementedError

    @property
    def data(self):
        final_data = b"{0}{1}".format(self._assemble_header(), self.body)
        return final_data

class HttpResponse(HttpMessage):
    def __init__(self):
        super(HttpResponse, self).__init__()

    def is_chunked_encoding(self):
        try:
            return "chunked" in self.header['Transfer-Encoding'].lower()
        except KeyError:
            return False

    def _assemble_header(self):
        http_header_query_str = "HTTP/{0} {1} {2}".format(self.version, self.status, RESPONSES[self.status])

        http_header_fields = [ "{0}: {1}".format(key, self.header[key]) for key in self.header ]

        http_header_list = [http_header_query_str]
        http_header_list.extend(http_header_fields)

        return "{0}\r\n\r\n".format("\r\n".join(http_header_list))

    def _assemble_body(self):
        raise NotImplementedError

    def _assemble_data(self):
        raise NotImplementedError

    @property
    def status_str(self):
        return "HTTP/{0} {1} {2}".format(self.version, self.status, RESPONSES[self.status])

    @property
    def data(self):
        if self.is_chunked_encoding():
            chunk_size = 1024
            chunks = [self.body[i:i+chunk_size] for i in range(0, len(self.body), chunk_size)]
            if not chunks:
                yield b"{0}".format(self._assemble_header())
            else:
                yield b"{0}{1:x}\r\n{2}\r\n".format(self._assemble_header(), len(chunks[0]), chunks.pop(0))
                for chunk in chunks:
                    yield b"{0:x}\r\n{1}\r\n".format(len(chunk), chunk)

            yield b"0\r\n\r\n"

        else:
            yield b"{0}{1}".format(self._assemble_header(), self.body)
