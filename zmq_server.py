import zmq

context = zmq.Context()
socket = context.socket(zmq.REP)
socket.bind("tcp://127.0.0.1:5581")

while True:
    data = socket.recv()
    print "zmq recv...."
    # print data
    socket.send(data)
