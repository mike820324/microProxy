from http_parser.parser import HttpParser
from status_codes import RESPONSES

class HttpMessage(object):
    def __init__(self):
        super(HttpMessage, self).__init__()
        self.parser = HttpParser()
        self.version = ""
        self.status = ""
        self.method = ""
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
            self.path = self.parser.get_path()
            self.query_string = self.parser.get_query_string()
            self.header = self.parser.get_headers()
            self.body = self.parser.recv_body()

class HttpRequest(HttpMessage):
    def __init__(self):
        super(HttpRequest, self).__init__()
    
    @property
    def data(self):
        http_query_str = "{0} {1}?{2} HTTP/{3}".format(self.method, self.path, self.query_string, self.version)
        http_header_list = [ "{0}: {1}".format(key, self.header[key]) for key in self.header]

        final_list = []
        final_list.append(http_query_str)
        final_list.extend(http_header_list)

        final_data = b"{0}\r\n\r\n{1}".format("\r\n".join(final_list), self.body)
        print final_data
        return final_data

class HttpResponse(HttpMessage):
    def __init__(self):
        super(HttpResponse, self).__init__()

    @property
    def data(self):
        http_query_str = "HTTP/{0} {1} {2}".format(self.version, self.status, RESPONSES[self.status])
        http_header_list = [ "{0}: {1}".format(key, self.header[key]) for key in self.header]

        final_list = []
        final_list.append(http_query_str)
        final_list.extend(http_header_list)

        final_data = b"{0}\r\n\r\n{1}".format("\r\n".join(final_list), self.body)
        return final_data
