import unittest
from microproxy.context import LayerContext


class TestLayerContext(unittest.TestCase):
    def test_invalid_mode(self):
        with self.assertRaises(ValueError):
            LayerContext(mode="test")
