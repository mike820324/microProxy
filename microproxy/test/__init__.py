import logging
from logging import NullHandler

logging.getLogger("protocol.http2").addHandler(NullHandler())
logging.getLogger("protocol.http2").propagate = False
logging.getLogger("tornado_ext").addHandler(NullHandler())
logging.getLogger("tornado_ext").propagate = False
logging.getLogger("tornado").addHandler(NullHandler())
logging.getLogger("tornado").propagate = False
