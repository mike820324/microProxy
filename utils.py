from zmq.eventloop.ioloop import IOLoop


def curr_loop():
    return IOLoop.current()
