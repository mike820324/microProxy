
class PluginContext(object):
    """
    PluinContext: Context used to communicate with plugin.
    """
    def __init__(self,
                 scheme,
                 host,
                 port,
                 path,
                 request,
                 response):

        super(PluginContext, self).__init__()
        self.scheme = scheme
        self.host = host
        self.port = port
        self.path = path
        self.request = request
        self.response = response
