import zmq
import json
import logging
logging.basicConfig()
logger = logging.getLogger("FlowControl")
logger.setLevel(logging.INFO)

context = zmq.Context()
socket = context.socket(zmq.REP)
socket.bind("tcp://127.0.0.1:5581")

while True:
    data = socket.recv()
    message = json.loads(data)
    if message["type"] == "response":
        status = message["resp_data"]["status"]
        method = message["req_data"]["method"]
        url = message["req_data"]["url"]
        logger.info("{0} {1} {2}".format(status, method, url))
    socket.send_json(message)
