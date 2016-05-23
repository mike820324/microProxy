from blinker import signal


class BaseInterceptor(object):
    signal_req = signal("interceptor_request")
    signal_resp = signal("interceptor_response")
    signal_record = signal("interceptor_record")

    def __init__(self):
        self._register_signal()

    def _register_signal(self):
        self.signal_req.connect(self.request)
        self.signal_resp.connect(self.response)
        self.signal_record.connect(self.record)

    def request(self, sender, **kargs):
        raise NotImplementedError

    def response(self, sender, **kargs):
        raise NotImplementedError

    def record(self, sender, **kargs):
        raise NotImplementedError
