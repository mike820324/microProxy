from base import Serializable


class TlsInfo(Serializable):
    def __init__(self,
                 version="",
                 cipher="",
                 sni="",
                 alpn="",
                 **kwargs):
        super(TlsInfo, self).__init__()
        self.version = version
        self.cipher = cipher
        self.sni = sni
        self.alpn = alpn
