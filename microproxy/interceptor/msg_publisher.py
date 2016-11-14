import json


class MsgPublisher(object):
    TOPIC = "message"

    def __init__(self, config, zmq_socket):
        super(MsgPublisher, self).__init__()
        self.zmq_socket = zmq_socket

    def publish(self, viewer_context):
        message = json.dumps(viewer_context.serialize())
        self.zmq_socket.send_multipart([
            self.TOPIC, message])
