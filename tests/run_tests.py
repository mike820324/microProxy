import unittest
import tornado.testing

TEST_MODULES = [
    "tests.test_http",
    "tests.test_config",
    "tests.test_proxy",
    "tests.layer.test_http1",
    "tests.layer.test_base",
    "tests.mode.test_transparent",
    "tests.mode.test_socks"
]


def all():
    return unittest.defaultTestLoader.loadTestsFromNames(TEST_MODULES)

if __name__ == "__main__":
    tornado.testing.main()
