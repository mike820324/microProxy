import unittest

from microproxy.context.base import parse_version


class TestBase(unittest.TestCase):
    def test_parse_release_version(self):
        self.assertEquals((0, 4, 0), parse_version("0.4.0"))

    def test_parse_dev_version(self):
        self.assertEquals((0, 4, 0), parse_version("0.4.0-dev"))
