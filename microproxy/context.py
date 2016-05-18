class Context(object):
    def __init__(self,
                 src_stream=None,
                 dest_stream=None,
                 interceptor=None,
                 host=None,
                 port=None,
                 config=None):
        self.src_stream = src_stream
        self.dest_stream = dest_stream
        self.interceptor = interceptor
        self.host = host
        self.port = port
        self.config = config

    def new_context(self,
                    src_stream=None,
                    dest_stream=None):
        if not src_stream:
            src_stream = self.src_stream
        if not dest_stream:
            dest_stream = self.dest_stream
        return Context(src_stream=src_stream,
                       dest_stream=dest_stream,
                       interceptor=self.interceptor,
                       host=self.host,
                       port=self.port,
                       config=self.config)
