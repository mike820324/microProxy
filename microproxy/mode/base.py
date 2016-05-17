class ProxyHandler(object):
    def __init__(self):
        super(ProxyHandler, self).__init__()

    def read_and_return_addr(self, src_stream):
        raise NotImplementedError()
