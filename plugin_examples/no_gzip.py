def on_request(request):
    try:
        if "gzip" in request.headers["Accept-Encoding"]:
            request.headers["Accept-Encoding"] = "deflate"
    except KeyError:
        pass
    return request
