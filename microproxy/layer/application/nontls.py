from copy import copy
from tornado import concurrent


class NonTlsLayer(object):
    def __init__(self, context):
        super(NonTlsLayer, self).__init__()
        self.context = copy(context)

    def process_and_return_context(self):
        self.context.scheme = "http"
        result = concurrent.Future()
        result.set_result(self.context)
        return result
