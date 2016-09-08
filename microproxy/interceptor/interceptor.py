from msg_publisher import MsgPublisher
from plugin_manager import PluginManager
from microproxy.context import ViewerContext, PluginContext


class Interceptor(object):
    def __init__(self, config, msg_publisher=None):
        self.msg_publisher = msg_publisher or MsgPublisher(config)
        self.plugin_manager = PluginManager(config)

    def request(self, layer_context, request):
        plugin_context = PluginContext(
            scheme=layer_context.scheme,
            host=layer_context.host,
            port=layer_context.port,
            path=request.path,
            request=request,
            response=None)

        new_plugin_context = self.plugin_manager.exec_request(plugin_context)
        return new_plugin_context

    def response(self, layer_context, request, response):
        plugin_context = PluginContext(
            scheme=layer_context.scheme,
            host=layer_context.host,
            port=layer_context.port,
            path=request.path,
            request=request,
            response=response)

        new_plugin_context = self.plugin_manager.exec_response(plugin_context)
        return new_plugin_context

    def publish(self, layer_context, request, response):
        viewer_context = ViewerContext(
            scheme=layer_context.scheme,
            host=layer_context.host,
            port=layer_context.port,
            path=request.path,
            request=request,
            response=response)

        self.msg_publisher.publish(viewer_context)
