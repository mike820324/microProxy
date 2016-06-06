import zmq
import json
from colored import fg, bg, attr


def construct_header_msg(request, response):
    req_headers = ["{0}: {1}".format(k, request["headers"][k]) for k in request["headers"]]
    resp_headers = ["{0}: {1}".format(k, response["headers"][k]) for k in response["headers"]]

    req_headers_str = fg("blue") + attr("bold") + "Request Headers:\n" + attr("reset")
    req_headers_str += bg("blue")
    req_headers_str += "\n".join(req_headers)
    req_headers_str += attr("reset")

    resp_headers_str = fg("blue") + attr("bold") + "Response Headers:\n" + attr("reset")
    resp_headers_str += bg("blue")
    resp_headers_str += "\n".join(resp_headers)
    resp_headers_str += attr("reset")

    return req_headers_str + "\n\n" + resp_headers_str


def construct_status_msg(request, response):
    host = request["headers"]["Host"]
    path = request["path"]

    if response["code"] < 400:
        status = fg("green") + attr("bold") + str(response["code"]) + attr("reset")
    else:
        status = fg("red") + attr("bold") + str(response["code"]) + attr("reset")

    method = request["method"]

    return "{0} {1} {2}{3}".format(status, method, host, path)


def construct_color_msg(message, verbose_level):
    request = message["request"]
    response = message["response"]
    status = construct_status_msg(request, response)
    header = construct_header_msg(request, response)

    if verbose_level == "status":
        return status + "\n"
    if verbose_level == "header":
        return status + "\n" + header + "\n"
    elif verbose_level == "body":
        raise NotImplementedError
    elif verbose_level == "all":
        raise NotImplementedError


def create_msg_channel(channel):
    context = zmq.Context()
    socket = context.socket(zmq.SUB)
    socket.connect(channel)
    socket.setsockopt(zmq.SUBSCRIBE, "")
    return socket


def start(config):
    socket = create_msg_channel(config["viewer_channel"])
    verbose_level = config["verbose_level"]
    print fg("blue") + attr("bold") + "MicroProxy Simple Viewer v0.0.2" + attr("reset")
    while True:
        try:
            data = socket.recv()
            message = json.loads(data)
            color_msg = construct_color_msg(message, verbose_level)
            print color_msg
        except KeyboardInterrupt:
            print fg("blue") + attr("bold") + "Closing Simple Viewer" + attr("reset")
            exit(0)
