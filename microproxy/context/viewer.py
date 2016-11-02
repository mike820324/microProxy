from http import HttpRequest, HttpResponse
from tls import TlsInfo
from base import Serializable, try_deserialize


class ViewerContext(Serializable):
    """
    ViewerContext: Context used to communicate with viewer.
    """
    def __init__(self,
                 scheme="",
                 host="",
                 port=0,
                 path="",
                 request=None,
                 response=None,
                 client_tls=None,
                 server_tls=None,
                 **kwargs):

        super(ViewerContext, self).__init__()
        self.scheme = scheme
        self.host = host
        self.port = port
        self.path = path

        self.request = try_deserialize(request, HttpRequest)
        self.response = try_deserialize(response, HttpResponse)
        self.client_tls = try_deserialize(client_tls, TlsInfo)
        self.server_tls = try_deserialize(server_tls, TlsInfo)
