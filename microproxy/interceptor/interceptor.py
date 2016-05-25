from copy import copy
from signal import signal_request, signal_publish, signal_response
from msg_publisher import MsgPublisher
from plugin_manager import PluginManager


class Interceptor(object):
    def __init__(self, config):
        self._register_signal()
        self.msg_publisher = MsgPublisher(config)
        self.plugin_manager = PluginManager(config)

    def _register_signal(self):
        signal_request.connect(self.request)
        signal_response.connect(self.response)
        signal_publish.connect(self.publish)

    def request(self, sender, request):
        request_msg = copy(request)
        request_msg = self.plugin_manager.exec_request(request_msg)
        return request_msg

    def response(self, sender, response):
        response_msg = copy(response)
        response_msg = self.plugin_manager.exec_response(response_msg)
        return response_msg

    def publish(self, sender, request, response):
        self.msg_publisher.publish(request, response)
