import unittest
import tornado.testing

TEST_MODULES = [
    "tests.test_proxy",
    "tests.test_http"
]


def all():
    return unittest.defaultTestLoader.loadTestsFromNames(TEST_MODULES)

if __name__ == "__main__":
    tornado.testing.main()
