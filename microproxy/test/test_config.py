import unittest
from mock import Mock

from microproxy.config import ConfigParserBuilder
from microproxy.config import (
    define_option, define_section, verify_config, gen_config)


class TestDefineSection(unittest.TestCase):
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


class TestDefineOption(unittest.TestCase):
    def test_str_type_option_without_default(self):
        config_info = {}
        define_option(option_info=config_info,
                      option_name="test",
                      help_str="test is a help",
                      option_type="str",
                      cmd_flags="--test")

        self.assertIn("test", config_info)
        self.assertEqual(config_info["test"]["help"], "test is a help")
        self.assertTrue(config_info["test"]["is_require"])
        self.assertEqual(config_info["test"]["type"], "str")
        self.assertTrue(config_info["test"]["is_require"])

    def test_default_option(self):
        config_info = {}
        try:
            define_option(option_info=config_info,
                          option_name="test",
                          help_str="test is a help",
                          option_type="str",
                          default="test1",
                          cmd_flags="--test")
        except:
            self.fail("define_option should not raise exception.")
        else:
            self.assertIn("test", config_info)
            self.assertFalse(config_info["test"]["is_require"])
            self.assertIs(config_info["test"]["default"], "test1")

    def test_cmd_flags_option(self):
        config_info = {}
        define_option(option_info=config_info,
                      option_name="test",
                      help_str="test is a help",
                      option_type="str",
                      cmd_flags="--test")

        self.assertIsInstance(config_info["test"]["cmd_flags"], list)
        self.assertIn("--test", config_info["test"]["cmd_flags"])

        config_info = {}
        define_option(option_info=config_info,
                      option_name="test",
                      help_str="test is a help",
                      option_type="str",
                      cmd_flags=["--test", "-t"])

        self.assertIsInstance(config_info["test"]["cmd_flags"], list)
        self.assertIn("--test", config_info["test"]["cmd_flags"])
        self.assertIn("-t", config_info["test"]["cmd_flags"])

    def test_choices_option(self):
        config_info = {}
        define_option(option_info=config_info,
                      option_name="test",
                      help_str="test is a help",
                      option_type="str",
                      choices=["socks", "proxy"],
                      cmd_flags="--test")

        self.assertIsInstance(config_info["test"]["choices"], list)
        self.assertIn("socks", config_info["test"]["choices"])
        self.assertIn("proxy", config_info["test"]["choices"])

    def test_list_type_option(self):
        config_info = {}
        define_option(option_info=config_info,
                      option_name="test",
                      help_str="test is a help",
                      option_type="list:str",
                      cmd_flags="--test")

        self.assertIn("test", config_info)
        self.assertEqual(config_info["test"]["help"], "test is a help")
        self.assertTrue(config_info["test"]["is_require"])
        self.assertEqual(config_info["test"]["type"], "list:str")

    def test_incorrect_option_info(self):
        with self.assertRaises(ValueError):
            define_option(option_info=None,
                          option_name="test",
                          help_str="test is a help",
                          option_type="str",
                          cmd_flags="--test")

    def test_incorrect_option_type(self):
        config_info = {}
        with self.assertRaises(ValueError):
            define_option(option_info=config_info,
                          option_name="test",
                          help_str="test is a help",
                          option_type="not_a_type",
                          cmd_flags="--test")

    def test_incorrect_list_type(self):
        config_info = {}
        with self.assertRaises(ValueError):
            define_option(option_info=config_info,
                          option_name="test",
                          help_str="test is a help",
                          option_type="list:abc",
                          cmd_flags="--test")

    def test_missing_list_type(self):
        config_info = {}
        with self.assertRaises(ValueError):
            define_option(option_info=config_info,
                          option_name="test",
                          help_str="test is a help",
                          option_type="list",
                          cmd_flags="--test")

    def test_incorrect_choices_type(self):
        config_info = {}
        with self.assertRaises(ValueError):
            define_option(option_info=config_info,
                          option_name="test",
                          help_str="test is a help",
                          option_type="str",
                          choices="hello",
                          cmd_flags="--test")


class TestConfig(unittest.TestCase):
    def setUp(self):
        self.config_field_info = {}
        define_option(option_info=self.config_field_info,
                      option_name="host",
                      help_str="Specify the proxy host",
                      default="127.0.0.1",
                      option_type="str",
                      cmd_flags="--host",
                      config_file_flags="proxy:host")

        define_option(option_info=self.config_field_info,
                      option_name="port",
                      help_str="Specify the proxy listening port",
                      option_type="int",
                      cmd_flags="--port",
                      config_file_flags="proxy:port")

        define_option(option_info=self.config_field_info,
                      option_name="http_port",
                      help_str="Add additional http port",
                      default="",
                      option_type="list:int",
                      cmd_flags="--http-port",
                      config_file_flags="proxy:http.port")

    def test_cmd_arguments(self):
        parser = ConfigParserBuilder.setup_cmd_parser(self.config_field_info)
        arguments = [
            "--host", "127.0.0.1",
            "--port", "8080",
            "--http-port", "5000,5001"
        ]
        config = vars(parser.parse_args(arguments))

        self.assertEqual(config["host"], "127.0.0.1")
        self.assertEqual(config["port"], "8080")
        self.assertEqual(config["http_port"], "5000,5001")

    def test_config_options_cmd(self):
        cmd_options = {
            "host": "127.0.0.1",
            "port": "8080",
            "http_port": "5000,5001"
        }
        ini_parser = Mock()
        ini_parser.items = Mock(return_value=[])
        config = gen_config(self.config_field_info, ini_parser, cmd_options)
        self.assertEqual(config["host"], "127.0.0.1")
        self.assertIsInstance(config["port"], int)
        self.assertEqual(config["port"], 8080)
        self.assertIsInstance(config["http_port"], list)
        self.assertListEqual(config["http_port"], [5000, 5001])

    def test_config_options_ini(self):
        ini_options = [
            ("host", "127.0.0.1"),
            ("port", "8080"),
            ("http.port", "5000,5001")
        ]

        def ini_parser_side_effect(section, name):
            for key, value in ini_options:
                if name == key:
                    return value

        ini_parser = Mock()
        ini_parser.get = Mock(side_effect=ini_parser_side_effect)
        config = gen_config(self.config_field_info, ini_parser, {})
        self.assertEqual(config["host"], "127.0.0.1")
        self.assertIsInstance(config["port"], int)
        self.assertEqual(config["port"], 8080)
        self.assertIsInstance(config["http_port"], list)
        self.assertListEqual(config["http_port"], [5000, 5001])

    def test_config_options_overwrite(self):
        cmd_options = {
            "host": "127.0.0.1",
            "port": "8080"
        }
        ini_options = [
            ("host", "0.0.0.0"),
            ("port", "8000"),
            ("http.port", "5000,5001")
        ]

        def ini_parser_side_effect(section, name):
            for key, value in ini_options:
                if name == key:
                    return value

        ini_parser = Mock()
        ini_parser.get = Mock(side_effect=ini_parser_side_effect)
        config = gen_config(self.config_field_info, ini_parser, cmd_options)
        self.assertEqual(config["host"], "127.0.0.1")
        self.assertIsInstance(config["port"], int)
        self.assertEqual(config["port"], 8080)
        self.assertIsInstance(config["http_port"], list)
        self.assertListEqual(config["http_port"], [5000, 5001])

    def test_missing_requre_field(self):
        config = {
            "host": "127.0.0.1",
            "http_port": [5000],
        }

        with self.assertRaises(KeyError):
            verify_config(self.config_field_info, config)

    def test_incorect_value(self):
        config = {
            "mode": "not_exist"
        }

        with self.assertRaises(KeyError):
            verify_config(self.config_field_info, config)

    def test_unknown_field(self):
        config = {
            "host": "127.0.0.1",
            "port": 5580,
            "http_port": [5000],
            "unknown_field": "yaya"
        }

        # NOTE: unknow field should just print warning message
        # should not raise eny exception
        verify_config(self.config_field_info, config)

if __name__ == "__main__":
    unittest.main()
