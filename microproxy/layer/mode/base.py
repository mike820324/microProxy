class ProxyHandler(object):
    def __init__(self):
        super(ProxyHandler, self).__init__()

    def create_dest_stream(self, host, port):
        raise NotImplementedError()
