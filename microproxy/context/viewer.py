from http import HttpRequest, HttpResponse
from tls import TlsInfo
from base import Serializable, parse_version
from microproxy.version import VERSION


_DEFAULT_VERSION = "0.4.0"


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
                 version=VERSION,
                 **kwargs):

        super(ViewerContext, self).__init__()
        self.scheme = scheme
        self.host = host
        self.port = port
        self.path = path
        self.version = version

        self.request = HttpRequest.deserialize(request)
        self.response = HttpResponse.deserialize(response)
        self.client_tls = TlsInfo.deserialize(client_tls)
        self.server_tls = TlsInfo.deserialize(server_tls)

    @classmethod
    def deserialize(cls, data):
        enrich_data(data)
        return ViewerContext(**data)


def enrich_data(data):
    if "version" not in data:
        data["version"] = _DEFAULT_VERSION

    while True:
        version = parse_version(data["version"])
        converter = converters.get(version, None)
        if converter:
            converter(data)
        else:
            break
    data["version"] = VERSION


def convert_040_041(ctx):
    # Could remove in the future
    ctx["version"] = "0.4.1"


converters = {
    (0, 4, 0): convert_040_041
}
