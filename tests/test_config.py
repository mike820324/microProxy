import unittest
from mock import Mock
from microproxy.config import Config


class ConfigTest(unittest.TestCase):
    def test_proxy_cmd_options(self):
        cmd_options = {
            "command_type": "proxy",
            "host": "127.0.0.1",
            "port": 8080,
            "mode": "socks",
            "http_port": "5000,5001",
            "https_port": "5002,5003",
            "viewer_channel": "tcp://*:5581"
        }
        ini_parser = Mock()
        ini_parser.items = Mock(return_value=[])
        config = Config(ini_parser, cmd_options)
        assert config["host"] == "127.0.0.1"
        assert config["port"] == 8080
        assert config["mode"] == "socks"
        assert config["http_port"] == "5000,5001"
        assert config["https_port"] == "5002,5003"
        assert config["viewer_channel"] == "tcp://*:5581"

    def test_proxy_ini_options(self):
        cmd_options = {
            "command_type": "proxy"
        }
        ini_options = [
            ("host", "127.0.0.1"),
            ("port", 8080),
            ("mode", "socks"),
            ("http.port", "5000,5001"),
            ("https.port", "5002,5003"),
            ("viewer.channel", "tcp://*:5581")
        ]

        ini_parser = Mock()
        ini_parser.items = Mock(return_value=ini_options)
        config = Config(ini_parser, cmd_options)
        assert config["host"] == "127.0.0.1"
        assert config["port"] == 8080
        assert config["mode"] == "socks"
        assert config["http_port"] == "5000,5001"
        assert config["https_port"] == "5002,5003"
        assert config["viewer_channel"] == "tcp://*:5581"

    def test_proxy_cmd_overwrite(self):
        cmd_options = {
            "command_type": "proxy",
            "host": "127.0.0.1",
            "port": 8080,
            "mode": "socks",
            "viewer-channel": "tcp://*:5581"
        }
        ini_options = [
            ("host", "0.0.0.0"),
            ("port", 8000),
            ("mode", "transparent"),
            ("http.port", "5000,5001"),
            ("https.port", "5002,5003"),
            ("viewer.channel", "tcp://*:5581")
        ]
        ini_parser = Mock()
        ini_parser.items = Mock(return_value=ini_options)
        config = Config(ini_parser, cmd_options)
        assert config["host"] == "127.0.0.1"
        assert config["port"] == 8080
        assert config["mode"] == "socks"
        assert config["http_port"] == "5000,5001"
        assert config["https_port"] == "5002,5003"
        assert config["viewer_channel"] == "tcp://*:5581"
