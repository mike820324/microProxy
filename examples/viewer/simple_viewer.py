# Simple Viewer Implementation for microProxy.
# Usage: python simple_viewer.py --viewer-channel tcp://127.0.0.1:5581

import zmq
import json
import argparse


def create_msg_channel(channel):
    context = zmq.Context()
    socket = context.socket(zmq.SUB)
    socket.connect(channel)
    socket.setsockopt(zmq.SUBSCRIBE, "")
    return socket


def main(channel):
    socket = create_msg_channel(channel)
    print "Simple Viewer Example"

    while True:
        try:
            # using zmq to get the viewer context
            data = socket.recv()
            message = json.loads(data)

            scheme = message["scheme"]
            host = message["host"]
            port = message["port"]
            path = message["path"]
            request = message["request"]
            response = message["response"]

            pretty_message = "{0:3} {1:8} {2}://{3}:{4}{5:50}".format(
                response["code"], request["method"], scheme, host, port, path)
            print pretty_message
        except KeyboardInterrupt:
            print "Bye Bye"
            exit(0)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Viewer Example")
    parser.add_argument(
        '--viewer-channel', dest="channel", required=True,
        help="zmq channel. ex. tcp://127.0.0.1:5581")
    args = parser.parse_args()

    main(args.channel)
