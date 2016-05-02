import ConfigParser
import argparse
import os.path


class Config(object):
    def __init__(self, file_config, cmd_config):
        if cmd_config["command_type"] == "proxy":
            self.file = {k.replace(".", "_"): v for k, v in file_config.items("Proxy")}
        elif cmd_config["command_type"] == "viewer":
            self.file = {k.replace(".", "_"): v for k, v in file_config.items("Viewer")}

        self.cmd = cmd_config

    def __getitem__(self, key):
        if key in self.cmd and self.cmd[key] is not None:
            return self.cmd[key]
        elif key in self.file and self.file[key] is not None:
            return self.file[key]
        else:
            raise KeyError


class ConfigBuilder(object):
    def __init__(self):
        self.file_parser = self.setup_file_parser()
        self.cmd_parser = self.setup_cmd_parser()

    def setup_file_parser(self):
        parser = ConfigParser.SafeConfigParser()
        return parser

    def setup_cmd_parser(self):
        parser = argparse.ArgumentParser(description="MicroProxy a http/https proxy interceptor.")
        parser.add_argument("--config-file",
                            default="./application.cfg",
                            help="Specify config file location")
        subparser = parser.add_subparsers(dest="command_type")

        proxy_parser = subparser.add_parser("proxy",
                                            help="Enable Proxy Server")
        proxy_parser.add_argument("--host",
                                  help="Specify the proxy host")
        proxy_parser.add_argument("--port",
                                  type=int,
                                  help="Specify the proxy listening port")
        proxy_parser.add_argument("--proxy-mode",
                                  choices=["socks", "transparent"],
                                  help="Speficy the proxy mode, currently support socks proxy and transparent proxy")
        proxy_parser.add_argument("--http-port",
                                  help="Add additional http port")
        proxy_parser.add_argument("--https-port",
                                  help="Add additional https port")
        proxy_parser.add_argument("--viewer-channel",
                                  help="Specify the viewer channel. ex. tcp://*:5581")

        viewer_parser = subparser.add_parser("viewer",
                                             help="Open MircorProxy Viewer")
        viewer_parser.add_argument("--viewer-mode",
                                   choices=["log"],
                                   help="Speicfy the viewer type")
        viewer_parser.add_argument("--viewer-channel",
                                  help="Specify the viewer channel. ex. tcp://127.0.0.1:5581")
        return parser

    def parse_config(self):
        cmd_config = self.cmd_parser.parse_args()
        config_file = cmd_config.config_file
        if not os.path.isfile(config_file):
            config_file = "./application.cfg"

        self.file_parser.read(config_file)
        return Config(self.file_parser, vars(cmd_config))
