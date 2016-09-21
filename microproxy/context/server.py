class ServerContext(object):
    """ServerContext: Context contains server state."""
    def __init__(self,
                 io_loop=None,
                 config=None,
                 interceptor=None,
                 cert_store=None):
        self.io_loop = io_loop
        self.config = config
        self.interceptor = interceptor
        self.cert_store = cert_store
