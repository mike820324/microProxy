import unittest
from mock import Mock

from microproxy.config import Config, ConfigParserBuilder, verify_config_or_raise_error
from microproxy.config import define_option, define_section


class DefineSectionTest(unittest.TestCase):
    def test_no_error(self):
        option_info = {}
        config_field_info = {}
        define_section(config_field_info=config_field_info,
                       section="test",
                       help_str="this is a test",
                       option_info=option_info)

        self.assertIn("test", config_field_info)
        self.assertIs(config_field_info["test"], option_info)

    def test_incorrect_config_field_info(self):
        option_info = {}
        with self.assertRaises(ValueError):
            define_section(config_field_info=None,
                           section="test",
                           help_str="this is a test",
                           option_info=option_info)

    def test_incorrect_option_info_type(self):
        config_field_info = {}
        with self.assertRaises(ValueError):
            define_section(config_field_info=config_field_info,
                           section="test",
                           help_str="this is a test",
                           option_info=None)


class DefineOptionTest(unittest.TestCase):
    def test_non_list_type_option(self):
        config_info = {}
        define_option(option_info=config_info,
                      option_name="test",
                      help_str="test is a help",
                      is_require=True,
                      option_type="string")

        self.assertIn("test", config_info)
        self.assertEqual(config_info["test"]["help"], "test is a help")
        self.assertTrue(config_info["test"]["is_require"])
        self.assertEqual(config_info["test"]["type"], "string")

    def test_cmd_flags_option(self):
        config_info = {}
        define_option(option_info=config_info,
                      option_name="test",
                      help_str="test is a help",
                      is_require=True,
                      option_type="string",
                      cmd_flags="--test")

        self.assertIsInstance(config_info["test"]["cmd_flags"], list)
        self.assertIn("--test", config_info["test"]["cmd_flags"])

        config_info = {}
        define_option(option_info=config_info,
                      option_name="test",
                      help_str="test is a help",
                      is_require=True,
                      option_type="string",
                      cmd_flags=["--test", "-t"])

        self.assertIsInstance(config_info["test"]["cmd_flags"], list)
        self.assertIn("--test", config_info["test"]["cmd_flags"])
        self.assertIn("-t", config_info["test"]["cmd_flags"])

    def test_choices_option(self):
        config_info = {}
        define_option(option_info=config_info,
                      option_name="test",
                      help_str="test is a help",
                      is_require=True,
                      option_type="string",
                      choices=["socks", "proxy"])

        self.assertIsInstance(config_info["test"]["choices"], list)
        self.assertIn("socks", config_info["test"]["choices"])
        self.assertIn("proxy", config_info["test"]["choices"])

    def test_list_type_option(self):
        config_info = {}
        define_option(option_info=config_info,
                      option_name="test",
                      help_str="test is a help",
                      is_require=True,
                      option_type="list",
                      list_type="string")

        self.assertIn("test", config_info)
        self.assertEqual(config_info["test"]["help"], "test is a help")
        self.assertTrue(config_info["test"]["is_require"])
        self.assertEqual(config_info["test"]["type"], "list")
        self.assertEqual(config_info["test"]["list_type"], "string")

    def test_default_option(self):
        config_info = {}
        define_option(option_info=config_info,
                      option_name="test",
                      help_str="test is a help",
                      is_require=False,
                      option_type="string",
                      default_value="test1")

        self.assertIs(config_info["test"]["default"], "test1")

    def test_incorrect_option_info(self):
        with self.assertRaises(ValueError):
            define_option(option_info=None,
                          option_name="test",
                          help_str="test is a help",
                          is_require=True,
                          option_type="string")

    def test_incorrect_option_type(self):
        config_info = {}
        with self.assertRaises(ValueError):
            define_option(option_info=config_info,
                          option_name="test",
                          help_str="test is a help",
                          is_require=True,
                          option_type="not_a_type")

    def test_incorrect_list_type(self):
        config_info = {}
        with self.assertRaises(ValueError):
            define_option(option_info=config_info,
                          option_name="test",
                          help_str="test is a help",
                          is_require=True,
                          option_type="list",
                          list_type="not_a_type")

    def test_missing_list_type(self):
        config_info = {}
        with self.assertRaises(ValueError):
            define_option(option_info=config_info,
                          option_name="test",
                          help_str="test is a help",
                          is_require=True,
                          option_type="list")

    def test_incorrect_choices_type(self):
        config_info = {}
        with self.assertRaises(ValueError):
            define_option(option_info=config_info,
                          option_name="test",
                          help_str="test is a help",
                          is_require=True,
                          option_type="string",
                          choices="hello")

    def test_missing_default_value(self):
        config_info = {}
        with self.assertRaises(ValueError):
            define_option(option_info=config_info,
                          option_name="test",
                          help_str="test is a help",
                          is_require=False,
                          option_type="list",
                          list_type="not_a_type")


class ConfigTest(unittest.TestCase):
    def setUp(self):
        proxy_option_info = {}
        define_option(option_info=proxy_option_info,
                      option_name="host",
                      help_str="Specify the proxy host",
                      is_require=False,
                      default_value="127.0.0.1",
                      option_type="string",
                      cmd_flags="--host")

        define_option(option_info=proxy_option_info,
                      option_name="port",
                      help_str="Specify the proxy listening port",
                      is_require=True,
                      option_type="int",
                      cmd_flags="--port")

        define_option(option_info=proxy_option_info,
                      option_name="http_port",
                      help_str="Add additional http port",
                      is_require=False,
                      default_value="",
                      option_type="list",
                      cmd_flags="--http-port",
                      list_type="int")

        viewer_option_info = {}
        define_option(option_info=viewer_option_info,
                      option_name="mode",
                      help_str="Specify the viewer type",
                      is_require=True,
                      option_type="string",
                      cmd_flags="--mode",
                      choices=["--mode"])

        self.config_field_info = {}
        define_section(config_field_info=self.config_field_info,
                       section="proxy",
                       option_info=proxy_option_info,
                       help_str="Open microproxy service")
        define_section(config_field_info=self.config_field_info,
                       section="viewer",
                       option_info=viewer_option_info,
                       help_str="Open viewer")

    def test_cmd_arguments(self):
        parser = ConfigParserBuilder.setup_cmd_parser(self.config_field_info)
        arguments = [
            "proxy",
            "--host", "127.0.0.1",
            "--port", "8080",
            "--http-port", "5000,5001"
        ]
        config = vars(parser.parse_args(arguments))

        self.assertEqual(config["command_type"], "proxy")
        self.assertEqual(config["host"], "127.0.0.1")
        self.assertEqual(config["port"], "8080")
        self.assertEqual(config["http_port"], "5000,5001")

        arguments = [
            "viewer",
            "--mode", "log"
        ]
        config = vars(parser.parse_args(arguments))

        self.assertEqual(config["command_type"], "viewer")
        self.assertEqual(config["mode"], "log")

    def test_config_options_cmd(self):
        cmd_options = {
            "command_type": "proxy",
            "host": "127.0.0.1",
            "port": "8080",
            "http_port": "5000,5001"
        }
        ini_parser = Mock()
        ini_parser.items = Mock(return_value=[])
        config = Config(self.config_field_info, ini_parser, cmd_options)
        self.assertEqual(config["command_type"], "proxy")
        self.assertEqual(config["host"], "127.0.0.1")
        self.assertIsInstance(config["port"], int)
        self.assertEqual(config["port"], 8080)
        self.assertIsInstance(config["http_port"], list)
        self.assertListEqual(config["http_port"], [5000, 5001])

    def test_config_options_ini(self):
        cmd_options = {
            "command_type": "proxy"
        }
        ini_options = [
            ("host", "127.0.0.1"),
            ("port", "8080"),
            ("http.port", "5000,5001")
        ]

        ini_parser = Mock()
        ini_parser.items = Mock(return_value=ini_options)
        config = Config(self.config_field_info, ini_parser, cmd_options)
        self.assertEqual(config["command_type"], "proxy")
        self.assertEqual(config["host"], "127.0.0.1")
        self.assertIsInstance(config["port"], int)
        self.assertEqual(config["port"], 8080)
        self.assertIsInstance(config["http_port"], list)
        self.assertListEqual(config["http_port"], [5000, 5001])

    def test_config_options_overwrite(self):
        cmd_options = {
            "command_type": "proxy",
            "host": "127.0.0.1",
            "port": "8080"
        }
        ini_options = [
            ("host", "0.0.0.0"),
            ("port", "8000"),
            ("http.port", "5000,5001")
        ]
        ini_parser = Mock()
        ini_parser.items = Mock(return_value=ini_options)
        config = Config(self.config_field_info, ini_parser, cmd_options)
        self.assertEqual(config["command_type"], "proxy")
        self.assertEqual(config["host"], "127.0.0.1")
        self.assertIsInstance(config["port"], int)
        self.assertEqual(config["port"], 8080)
        self.assertIsInstance(config["http_port"], list)
        self.assertListEqual(config["http_port"], [5000, 5001])

    def test_missing_requre_field(self):
        cmd_options = {
            "command_type": "proxy",
            "host": "127.0.0.1"
        }

        ini_options = []
        ini_parser = Mock()
        ini_parser.items = Mock(return_value=ini_options)

        config = Config(self.config_field_info, ini_parser, cmd_options)

        with self.assertRaises(KeyError):
            verify_config_or_raise_error(self.config_field_info, config)

    def test_incorect_value(self):
        cmd_options = {
            "command_type": "viewer",
            "mode": "not_exist"
        }

        ini_options = []
        ini_parser = Mock()
        ini_parser.items = Mock(return_value=ini_options)

        config = Config(self.config_field_info, ini_parser, cmd_options)

        with self.assertRaises(ValueError):
            verify_config_or_raise_error(self.config_field_info, config)
