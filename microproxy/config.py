import ConfigParser
import argparse
import os.path

from microproxy.utils import get_logger
logger = get_logger(__name__)

ConfigProxyFields = {
    "host": {
        "cmd_flags": ["--host"],
        "help": "Specify the proxy host",
        "type": "string"
    },
    "port": {
        "cmd_flags": ["--port"],
        "help": "Specify the proxy listening port",
        "type": "int"
    },
    "mode": {
        "cmd_flags": ["--mode"],
        "help": "Speficy the proxy mode, currently support socks proxy and transparent proxy",
        "choices": ["socks", "transparent"],
        "type": "string"
    },
    "http_port": {
        "cmd_flags": ["--http-port"],
        "help": "Add additional http port",
        "type": "int",
        "is_list": True
    },
    "https_port": {
        "cmd_flags": ["--https-port"],
        "help": "Add additional https port",
        "type": "int",
        "is_list": True
    },
    "viewer_channel": {
        "cmd_flags": ["--viewer-channel"],
        "help": "Specify the viewer channel. ex. tcp://*:5581",
        "type": "string"
    },
}

ConfigViewerFields = {
    "mode": {
        "cmd_flags": ["--mode"],
        "help": "Sepcify the viewer type",
        "choices": ["log"],
        "type": "string"
    },
    "viewer_channel": {
        "cmd_flags": ["--viewer-channel"],
        "help": "Specify the viewer channel. ex. tcp://127.0.0.1:5581",
        "type": "string"
    }
}

ConfigSections = {
    "proxy": ConfigProxyFields,
    "viewer": ConfigViewerFields
}


class Config(object):
    def __init__(self, file_config, cmd_config):
        command_type = cmd_config["command_type"]
        fieldInfos = ConfigSections[command_type]
        file_config = {k.replace(".", "_"): v for k, v in file_config.items(command_type)}
        file_config.update(self.typeValidation(file_config, fieldInfos))

        cmd_config = {k: v for k, v in cmd_config.iteritems() if v is not None}
        tmp_config = {k: v for k, v in cmd_config.iteritems() if k != "command_type" and k != "config_file"}
        cmd_config.update(self.typeValidation(tmp_config, fieldInfos))

        self.__config = file_config.copy()
        self.__config.update(cmd_config)

    def typeValidation(self, config, fieldInfos):
        new_config = {}
        for field in config:
            if field not in fieldInfos:
                logger.warning("Unknonw Config Field {0}".format(field))
                continue

            try:
                if config[field] not in fieldInfos[field]["choices"]:
                    logger.error("Unknonw Config Value {0} For Field {1}".format(config[field], field))
                    continue
            except KeyError:
                pass

            if "is_list" in fieldInfos[field] and fieldInfos[field]["is_list"]:
                if fieldInfos[field]["type"] == "int":
                    new_config[field] = map(int, config[field].split(","))
                else:
                    new_config[field] = config[field].split(",")
            else:
                if fieldInfos[field]["type"] == "int":
                    new_config[field] = int(config[field])
                else:
                    new_config[field] = config[field]

        return new_config

    def __getitem__(self, key):
        try:
            return self.__config[key]
        except KeyError:
            raise


class ConfigParserBuilder(object):
    @staticmethod
    def setup_ini_parser():
        parser = ConfigParser.SafeConfigParser()
        return parser

    @staticmethod
    def setup_cmd_parser():
        parser = argparse.ArgumentParser(description="MicroProxy a http/https proxy interceptor.")

        parser.add_argument("--config-file",
                            default="./application.cfg",
                            help="Specify config file location")
        subparser = parser.add_subparsers(dest="command_type")

        # Proxy service options
        proxy_parser = subparser.add_parser("proxy",
                                            help="Enable Proxy Server")

        for field_name, field_info in ConfigProxyFields.iteritems():
            if "cmd_flags" not in field_info:
                continue

            proxy_parser.add_argument(*field_info["cmd_flags"],
                                      dest=field_name,
                                      help=field_info["help"])

        # Viewer Service options
        viewer_parser = subparser.add_parser("viewer",
                                             help="Open MircorProxy Viewer")

        for field_name, field_info in ConfigViewerFields.iteritems():
            if "cmd_flags" not in field_info:
                continue

            viewer_parser.add_argument(*field_info["cmd_flags"],
                                       dest=field_name,
                                       help=field_info["help"])
        return parser


def parse_config():
    cmd_parser = ConfigParserBuilder.setup_cmd_parser()
    cmd_config = cmd_parser.parse_args()

    config_file = cmd_config.config_file
    if not os.path.isfile(config_file):
        config_file = "./application.cfg"

    ini_parser = ConfigParserBuilder.setup_ini_parser()
    ini_parser.read(config_file)
    return Config(ini_parser, vars(cmd_config))
