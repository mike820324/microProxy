class LayerContext(object):
    """
    LayerContext: Context used to communicate with different layer.
    """
    def __init__(self,
                 mode,
                 src_stream=None,
                 dest_stream=None,
                 scheme=None,
                 host=None,
                 port=None):
        if mode not in ("socks", "transparent", "replay"):
            raise ValueError("incorrect mode value")

        self.mode = mode
        self.src_stream = src_stream
        self.dest_stream = dest_stream
        self.scheme = scheme
        self.host = host
        self.port = port
