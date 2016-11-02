from base import Serializable


class Tls(Serializable):
    def __init__(self,
                 cipher="",
                 sni="",
                 alpn="",
                 **kwargs):
        super(Tls, self).__init__()
        self.cipher = cipher
        self.sni = sni
        self.alpn = alpn
