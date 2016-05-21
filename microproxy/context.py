class Context(object):
    def __init__(self,
                 src_stream=None,
                 dest_stream=None,
                 host=None,
                 port=None,
                 config=None,
                 layer_manager=None):
        self.src_stream = src_stream
        self.dest_stream = dest_stream
        self.host = host
        self.port = port
        self.config = config
        self.layer_manager = layer_manager

    def new_context(self,
                    src_stream=None,
                    dest_stream=None):
        if not src_stream:
            src_stream = self.src_stream
        if not dest_stream:
            dest_stream = self.dest_stream
        return Context(src_stream=src_stream,
                       dest_stream=dest_stream,
                       host=self.host,
                       port=self.port,
                       config=self.config,
                       layer_manager=self.layer_manager)
