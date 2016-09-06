import unittest

from microproxy.command_line import create_proxy_options, create_tui_viewer_options, create_console_viewer_options
from microproxy.config import define_option


class CommandLineTest(unittest.TestCase):
    def test_proxy_command(self):
        proxy_options = {}
        define_option(option_info=proxy_options,
                      option_name="host",
                      help_str="Specify the proxy host",
                      default="127.0.0.1",
                      option_type="string",
                      cmd_flags="--host")

        define_option(option_info=proxy_options,
                      option_name="port",
                      help_str="Specify the proxy listening port",
                      default="5580",
                      option_type="int",
                      cmd_flags="--port")

        define_option(option_info=proxy_options,
                      option_name="mode",
                      help_str="Speficy the proxy mode, currently support socks proxy and transparent proxy",
                      option_type="string",
                      cmd_flags="--mode",
                      choices=["socks", "transparent"])

        define_option(option_info=proxy_options,
                      option_name="http_port",
                      help_str="Add additional http port",
                      default="",
                      option_type="list",
                      cmd_flags="--http-port",
                      list_type="int")

        define_option(option_info=proxy_options,
                      option_name="https_port",
                      help_str="Add additional https port",
                      default="",
                      option_type="list",
                      cmd_flags="--https-port",
                      list_type="int")

        define_option(option_info=proxy_options,
                      option_name="plugins",
                      help_str="Load plugins",
                      default="",
                      option_type="list",
                      cmd_flags="--plugins",
                      list_type="string")

        define_option(option_info=proxy_options,
                      option_name="viewer_channel",
                      help_str="Specify the viewer channel. ex. tcp://*:5581",
                      option_type="string",
                      cmd_flags="--viewer-channel")

        define_option(option_info=proxy_options,
                      option_name="certfile",
                      help_str="Specify the certificate file",
                      option_type="string",
                      cmd_flags="--cert-file")

        define_option(option_info=proxy_options,
                      option_name="keyfile",
                      help_str="Specify the private key file",
                      option_type="string",
                      cmd_flags="--key-file")

        define_option(option_info=proxy_options,
                      option_name="events_channel",
                      help_str="Specify the events channel. ex. tcp://*:5582",
                      option_type="string",
                      default="tcp://127.0.0.1:5582",  # Note: Make default to only accept local to access it
                      cmd_flags="--events-channel")

        define_option(option_info=proxy_options,
                      option_name="insecure",
                      help_str="Specify the private key file",
                      option_type="string",
                      default="no",
                      choices=["yes", "no"],
                      cmd_flags="--insecure")

        define_option(option_info=proxy_options,
                      option_name="client_certs",
                      help_str="Specify the location of trusted ca pem file",
                      option_type="string",
                      default="",
                      cmd_flags="--client-certs")

        config = create_proxy_options()
        for options_key in config:
            self.assertIn(options_key, proxy_options)

    def test_console_command(self):
        options = {}

        define_option(option_info=options,
                      option_name="proxy_host",
                      help_str="Specify the proxy host. ex. tcp://127.0.0.1",
                      option_type="string",
                      cmd_flags="--proxy-host")

        define_option(option_info=options,
                      option_name="viewer_port",
                      help_str="Specify the viewer channel port. ex. 5581",
                      option_type="int",
                      cmd_flags="--viewer-channel-port")

        define_option(option_info=options,
                      option_name="events_port",
                      help_str="Specify the events channel port. ex. 5582",
                      option_type="int",
                      cmd_flags="--events-channel-port")

        define_option(option_info=options,
                      option_name="verbose_level",
                      help_str="Specify verbose level. (header, body, all)",
                      option_type="string",
                      cmd_flags="--verbose-level",
                      default="status",
                      choices=["status", "header", "body", "all"])

        define_option(option_info=options,
                      option_name="replay_file",
                      help_str="Specify replay file",
                      option_type="string",
                      default="",
                      cmd_flags="--replay-file")

        define_option(option_info=options,
                      option_name="dump_file",
                      help_str="Specify dump file",
                      option_type="string",
                      default="",
                      cmd_flags="--dump-file")

        config = create_console_viewer_options()

        for option_key in config:
            self.assertIn(option_key, options)

    def test_tui_command(self):
        options = {}

        define_option(option_info=options,
                      option_name="viewer_channel",
                      help_str="Specify the viewer channel. ex. tcp://127.0.0.1:5581",
                      option_type="string",
                      cmd_flags="--viewer-channel")

        define_option(option_info=options,
                      option_name="events_channel",
                      help_str="Specify the events channel. ex. tcp://127.0.0.1:5582",
                      option_type="string",
                      default="tcp://127.0.0.1:5582",
                      cmd_flags="--events-channel")

        define_option(option_info=options,
                      option_name="replay_file",
                      help_str="Specify a replay script file",
                      option_type="string",
                      default="",
                      cmd_flags="--replay-file")

    define_option(option_info=options,
                  option_name="max_width",
                  help_str="Specify a replay script file",
                  option_type="int",
                  default=80,
                  cmd_flags="--max-width")

        config = create_tui_viewer_options()

        for option_key in config:
            self.assertIn(option_key, options)
