import unittest
import tornado.testing

TEST_MODULES = [
    "microproxy.test.test_config",
    "microproxy.test.context.test_http",
    "microproxy.test.layer.test_manager",
    "microproxy.test.layer.test_forward",
    "microproxy.test.layer.test_http1",
    "microproxy.test.layer.test_socks",
    "microproxy.test.viewer.test_console",
    "microproxy.test.event.test_manager",
    "microproxy.test.event.test_client",
    "microproxy.test.protocol.test_http1"
]


def all():
    return unittest.defaultTestLoader.loadTestsFromNames(TEST_MODULES)

if __name__ == "__main__":
    tornado.testing.main()
