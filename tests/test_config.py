import unittest
from mock import Mock
from microproxy.config import Config, ConfigParserBuilder, verify_config_or_raise_error


class ConfigTest(unittest.TestCase):
    def test_cmd_proxy_arguments(self):
        parser = ConfigParserBuilder.setup_cmd_parser()
        arguments = [
            "proxy",
            "--host", "127.0.0.1",
            "--port", "8080",
            "--mode", "socks",
            "--http-port", "5000,5001",
            "--https-port", "5002,5003",
            "--viewer-channel", "tcp://*:5581"
        ]
        config = vars(parser.parse_args(arguments))

        assert config["command_type"] == "proxy"
        assert config["host"] == "127.0.0.1"
        assert config["port"] == "8080"
        assert config["mode"] == "socks"
        assert config["http_port"] == "5000,5001"
        assert config["https_port"] == "5002,5003"
        assert config["viewer_channel"] == "tcp://*:5581"

    def test_cmd_viewer_arguments(self):
        parser = ConfigParserBuilder.setup_cmd_parser()
        arguments = [
            "viewer",
            "--mode", "log",
            "--viewer-channel", "tcp://127.0.0.1:5581"
        ]
        config = vars(parser.parse_args(arguments))

        assert config["command_type"] == "viewer"
        assert config["mode"] == "log"
        assert config["viewer_channel"] == "tcp://127.0.0.1:5581"

    def test_config_options_cmd(self):
        cmd_options = {
            "command_type": "proxy",
            "host": "127.0.0.1",
            "port": "8080",
            "mode": "socks",
            "http_port": "5000,5001",
            "https_port": "5002,5003",
            "viewer_channel": "tcp://*:5581"
        }
        ini_parser = Mock()
        ini_parser.items = Mock(return_value=[])
        config = Config(ini_parser, cmd_options)
        assert config["command_type"] == "proxy"
        assert config["host"] == "127.0.0.1"
        assert config["port"] == 8080
        assert config["mode"] == "socks"
        assert config["http_port"] == [5000, 5001]
        assert config["https_port"] == [5002, 5003]
        assert config["viewer_channel"] == "tcp://*:5581"

    def test_config_options_ini(self):
        cmd_options = {
            "command_type": "proxy"
        }
        ini_options = [
            ("host", "127.0.0.1"),
            ("port", "8080"),
            ("mode", "socks"),
            ("http.port", "5000,5001"),
            ("https.port", "5002,5003"),
            ("viewer.channel", "tcp://*:5581")
        ]

        ini_parser = Mock()
        ini_parser.items = Mock(return_value=ini_options)
        config = Config(ini_parser, cmd_options)
        assert config["command_type"] == "proxy"
        assert config["host"] == "127.0.0.1"
        assert config["port"] == 8080
        assert config["mode"] == "socks"
        assert config["http_port"] == [5000, 5001]
        assert config["https_port"] == [5002, 5003]
        assert config["viewer_channel"] == "tcp://*:5581"

    def test_config_options_overwrite(self):
        cmd_options = {
            "command_type": "proxy",
            "host": "127.0.0.1",
            "port": "8080",
            "mode": "socks",
            "viewer_channel": "tcp://*:5581"
        }
        ini_options = [
            ("host", "0.0.0.0"),
            ("port", "8000"),
            ("mode", "transparent"),
            ("http.port", "5000,5001"),
            ("https.port", "5002,5003"),
            ("viewer.channel", "tcp://*:5581")
        ]
        ini_parser = Mock()
        ini_parser.items = Mock(return_value=ini_options)
        config = Config(ini_parser, cmd_options)
        assert config["command_type"] == "proxy"
        assert config["host"] == "127.0.0.1"
        assert config["port"] == 8080
        assert config["mode"] == "socks"
        assert config["http_port"] == [5000, 5001]
        assert config["https_port"] == [5002, 5003]
        assert config["viewer_channel"] == "tcp://*:5581"

    def test_missing_requre_field(self):
        cmd_options = {
            "command_type": "proxy",
            "host": "127.0.0.1",
            "mode": "socks",
            "viewer_channel": "tcp://*:5581"
        }

        ini_options = []
        ini_parser = Mock()
        ini_parser.items = Mock(return_value=ini_options)

        config = Config(ini_parser, cmd_options)

        with self.assertRaises(KeyError):
            verify_config_or_raise_error(config)

    def test_incorect_value(self):
        cmd_options = {
            "command_type": "proxy",
            "host": "127.0.0.1",
            "port": "5580",
            "mode": "not_exist",
            "viewer_channel": "tcp://*:5581"
        }

        ini_options = []
        ini_parser = Mock()
        ini_parser.items = Mock(return_value=ini_options)

        config = Config(ini_parser, cmd_options)

        with self.assertRaises(ValueError):
            verify_config_or_raise_error(config)
