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
