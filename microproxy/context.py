class Context(object):
    def __init__(self,
                 src_stream=None,
                 dest_stream=None,
                 interceptor=None,
                 host=None,
                 port=None):
        self.src_stream = src_stream
        self.dest_stream = dest_stream
        self.interceptor = interceptor
        self.host = host
        self.port = port
