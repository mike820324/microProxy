from microproxy.context.http import HttpHeaders


def on_request(plugin_context):
    if plugin_context.scheme == "h2":
        return plugin_context

    try:
        headers = plugin_context.request.headers.get_dict()
        headers["Accept-Encoding"] = "deflate"

        new_headers = HttpHeaders(headers=headers)
        plugin_context.request.headers = new_headers
    except Exception as e:
        print e
    return plugin_context
