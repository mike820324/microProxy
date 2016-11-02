from microproxy.context import ViewerContext, PluginContext


class Interceptor(object):
    def __init__(self, plugin_manager=None, msg_publisher=None):
        self.msg_publisher = msg_publisher
        self.plugin_manager = plugin_manager

    def request(self, layer_context, request):
        plugin_context = PluginContext(
            scheme=layer_context.scheme,
            host=layer_context.host,
            port=layer_context.port,
            path=request.path,
            request=request,
            response=None)

        if self.plugin_manager is None:
            return plugin_context

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

        if self.plugin_manager is None:
            return plugin_context

        new_plugin_context = self.plugin_manager.exec_response(plugin_context)
        return new_plugin_context

    def publish(self, layer_context, request, response):
        if self.msg_publisher is None:
            return

        viewer_context = ViewerContext(
            scheme=layer_context.scheme,
            host=layer_context.host,
            port=layer_context.port,
            path=request.path,
            request=request,
            response=response,
            client_tls=layer_context.client_tls,
            server_tls=layer_context.server_tls)

        self.msg_publisher.publish(viewer_context)
