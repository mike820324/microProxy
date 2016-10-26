import unittest

from microproxy.command_line import create_proxy_options, create_tui_viewer_options, create_console_viewer_options
from microproxy.config import define_option


class CommandLineTest(unittest.TestCase):
    def test_proxy_command(self):
        proxy_option_info = {}
        define_option(option_info=proxy_option_info,
                      option_name="host",
                      help_str="Specify the proxy host",
                      default="127.0.0.1",
                      option_type="str",
                      cmd_flags="--host",
                      config_file_flags="proxy:host")

        define_option(option_info=proxy_option_info,
                      option_name="port",
                      help_str="Specify the proxy listening port",
                      default="5580",
                      option_type="int",
                      cmd_flags="--port",
                      config_file_flags="proxy:port")

        define_option(option_info=proxy_option_info,
                      option_name="mode",
                      help_str="Speficy the proxy mode, currently support socks proxy and transparent proxy",
                      option_type="str",
                      cmd_flags="--mode",
                      config_file_flags="proxy:mode",
                      choices=["socks", "transparent"])

        define_option(option_info=proxy_option_info,
                      option_name="http_port",
                      help_str="Add additional http port",
                      default="",
                      option_type="list:int",
                      cmd_flags="--http-port",
                      config_file_flags="proxy:http.port"
                      )

        define_option(option_info=proxy_option_info,
                      option_name="https_port",
                      help_str="Add additional https port",
                      default="",
                      option_type="list:int",
                      cmd_flags="--https-port",
                      config_file_flags="proxy:https.port")

        define_option(option_info=proxy_option_info,
                      option_name="certfile",
                      help_str="Specify the certificate file",
                      option_type="str",
                      cmd_flags="--cert-file",
                      config_file_flags="proxy:certfile")

        define_option(option_info=proxy_option_info,
                      option_name="keyfile",
                      help_str="Specify the private key file",
                      option_type="str",
                      cmd_flags="--key-file",
                      config_file_flags="proxy:keyfile")

        define_option(option_info=proxy_option_info,
                      option_name="viewer_channel",
                      help_str="Specify the viewer channel. ex. tcp://*:5581",
                      option_type="str",
                      cmd_flags="--viewer-channel",
                      config_file_flags="channel:viewer")

        define_option(option_info=proxy_option_info,
                      option_name="events_channel",
                      help_str="Specify the events channel. ex. tcp://*:5582",
                      option_type="str",
                      default="tcp://127.0.0.1:5582",  # Note: Make default to only accept local to access it
                      cmd_flags="--events-channel",
                      config_file_flags="channel:events")

        define_option(option_info=proxy_option_info,
                      option_name="plugins",
                      help_str="Load plugins",
                      default="",
                      option_type="list:str",
                      cmd_flags="--plugins",
                      config_file_flags="advanced:plugins")

        define_option(option_info=proxy_option_info,
                      option_name="client_certs",
                      help_str="Specify the location of trusted ca pem file",
                      option_type="str",
                      default="",
                      cmd_flags="--client-certs",
                      config_file_flags="advanced:client.certs")

        define_option(option_info=proxy_option_info,
                      option_name="insecure",
                      help_str="This option make the proxy connect to inscure SSL connections.",
                      option_type="bool",
                      default=False,
                      cmd_flags=["--insecure", "-k"])

        config = create_proxy_options()
        for options_key in config:
            self.assertIn(options_key, proxy_option_info)

    def test_console_command(self):
        console_viewer_option_info = {}

        define_option(option_info=console_viewer_option_info,
                      option_name="proxy_host",
                      help_str="Specify the proxy host. ex. tcp://127.0.0.1",
                      option_type="str",
                      cmd_flags="--proxy-host",
                      config_file_flags="channel:host")

        define_option(option_info=console_viewer_option_info,
                      option_name="viewer_port",
                      help_str="Specify the viewer channel port. ex. 5581",
                      option_type="int",
                      cmd_flags="--viewer-channel-port",
                      config_file_flags="channel:viewer.port")

        define_option(option_info=console_viewer_option_info,
                      option_name="events_port",
                      help_str="Specify the events channel port. ex. 5582",
                      option_type="int",
                      cmd_flags="--events-channel-port",
                      config_file_flags="channel:events.port")

        define_option(option_info=console_viewer_option_info,
                      option_name="verbose_level",
                      help_str="Specify verbose level. (header, body, all)",
                      option_type="str",
                      cmd_flags="--verbose-level",
                      default="status",
                      choices=["status", "header", "body", "all"])

        define_option(option_info=console_viewer_option_info,
                      option_name="replay_file",
                      help_str="Specify replay file",
                      option_type="str",
                      default="",
                      cmd_flags="--replay-file")

        define_option(option_info=console_viewer_option_info,
                      option_name="dump_file",
                      help_str="Specify dump file",
                      option_type="str",
                      default="",
                      cmd_flags="--dump-file")

        config = create_console_viewer_options()

        for option_key in config:
            self.assertIn(option_key, console_viewer_option_info)

    def test_tui_command(self):
        tui_viewer_option_info = {}

        define_option(option_info=tui_viewer_option_info,
                      option_name="viewer_channel",
                      help_str="Specify the viewer channel. ex. tcp://127.0.0.1:5581",
                      option_type="str",
                      cmd_flags="--viewer-channel",
                      config_file_flags="channel:viewer")

        define_option(option_info=tui_viewer_option_info,
                      option_name="events_channel",
                      help_str="Specify the events channel. ex. tcp://127.0.0.1:5582",
                      option_type="str",
                      cmd_flags="--events-channel",
                      config_file_flags="channel:events")

        define_option(option_info=tui_viewer_option_info,
                      option_name="replay_file",
                      help_str="Specify a replay script file",
                      option_type="str",
                      default="",
                      cmd_flags="--replay-file")

        config = create_tui_viewer_options()

        for option_key in config:
            self.assertIn(option_key, tui_viewer_option_info)
