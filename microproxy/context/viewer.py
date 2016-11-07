from http import HttpRequest, HttpResponse
from tls import TlsInfo
from base import Serializable, try_deserialize, parse_version
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

        self.request = try_deserialize(request, HttpRequest)
        self.response = try_deserialize(response, HttpResponse)
        self.client_tls = try_deserialize(client_tls, TlsInfo)
        self.server_tls = try_deserialize(server_tls, TlsInfo)


def parse(data):
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
    return ViewerContext(**data)


def convert_040_041(ctx):
    # Could remove in the future
    ctx["version"] = "0.4.1"


converters = {
    (0, 4, 0): convert_040_041
}
