import unittest
import platform

from test_http import HttpTest
from test_proxy import SocksProxyHandlerTest

# TransparentProxyHandler only implement for linux
if platform.system() == "Linux":
    from test_proxy import TranparentProxyHandlerTest

if __name__ == "__main__":
    unittest.main()
