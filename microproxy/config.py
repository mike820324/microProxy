import ConfigParser
import argparse
import os.path

from microproxy.utils import get_logger
logger = get_logger(__name__)


class Config(object):
    def __init__(self, config_field_info, file_config, cmd_config):
        command_type = cmd_config["command_type"]
        optionInfos = config_field_info[command_type]

        file_config = {k.replace(".", "_"): v for k, v in file_config.items(command_type)}
        cmd_config = {k: v for k, v in cmd_config.iteritems() if v is not None and k != "config_file"}
        self.__config = file_config.copy()
        self.__config.update(cmd_config)
        self.__config.update(self.appendDefault(self.__config, optionInfos))
        self.__config.update(self.typeTransform(self.__config, optionInfos))

    def appendDefault(self, config, optionInfo):
        fields = [field for field in optionInfo if field not in config and not optionInfo[field]["is_require"]]
        options = {field: optionInfo[field]["default"] for field in fields}
        return options

    def typeTransform(self, config, optionInfo):
        new_config = {}
        for field in config:
            if field not in optionInfo:
                continue

            if optionInfo[field]["type"] == "int":
                new_config[field] = int(config[field])

            elif optionInfo[field]["type"] == "list":
                values = [value for value in config[field].split(",") if len(value) > 0]
                if optionInfo[field]["list_type"] == "int":
                    new_config[field] = map(int, values)
                elif optionInfo[field]["list_type"] == "string":
                    new_config[field] = values

            else:
                new_config[field] = config[field]

        return new_config

    def __getitem__(self, key):
        try:
            return self.__config[key]
        except KeyError:
            raise

    def __iter__(self):
        return iter(self.__config)


class ConfigParserBuilder(object):
    @staticmethod
    def setup_ini_parser():
        parser = ConfigParser.SafeConfigParser()
        return parser

    @staticmethod
    def setup_cmd_parser(config_field_info):
        parser = argparse.ArgumentParser(description="MicroProxy a http/https proxy interceptor.")

        parser.add_argument("--config-file",
                            default="./application.cfg",
                            help="Specify config file location")
        subparser = parser.add_subparsers(dest="command_type")

        for section in config_field_info:
            sub_parser = subparser.add_parser(section)

            for field_name, field_info in config_field_info[section].iteritems():
                if "cmd_flags" not in field_info:
                    continue
                sub_parser.add_argument(*field_info["cmd_flags"],
                                        dest=field_name,
                                        help=field_info["help"])

        return parser


def define_section(config_field_info,
                   section,
                   help_str,
                   option_info):
    if not isinstance(option_info, dict):
        raise ValueError("Expect option_info as a dictionary")
    if not isinstance(config_field_info, dict):
        raise ValueError("Expect config_field_info as a dictionary")

    config_field_info[section] = option_info


def define_option(option_info,
                  option_name,
                  help_str,
                  option_type,
                  default=None,
                  cmd_flags=None,
                  choices=None,
                  list_type=None
                  ):

    if not isinstance(option_info, dict):
        raise ValueError("Expect option_info as a dictionary")

    if option_type not in ["string", "boolean", "int", "list"]:
        raise ValueError("Unsupport type : {0}".format(option_type))

    if choices is not None and not isinstance(choices, list):
        raise ValueError("choices should be a list object")

    option = {
        option_name: {
            "help": help_str,
            "type": option_type
        }
    }

    if default is not None:
        option[option_name]["is_require"] = False
        option[option_name]["default"] = default
    else:
        option[option_name]["is_require"] = True

    if cmd_flags:
        if isinstance(cmd_flags, str):
            option[option_name]["cmd_flags"] = [cmd_flags]
        elif isinstance(cmd_flags, list):
            option[option_name]["cmd_flags"] = cmd_flags

    if choices:
        option[option_name]["choices"] = choices

    if option_type == "list":
        if not list_type:
            raise ValueError("Require list_type for option_type list")
        if list_type not in ["string", "boolean", "int"]:
            raise ValueError("Unsupport list type : {0}".format(list_type))

        option[option_name]["list_type"] = list_type

    option_info.update(option)


def verify_config(config_field_info, config):
    fieldInfos = config_field_info[config["command_type"]]
    require_fields = [k for k, v in fieldInfos.iteritems() if v["is_require"]]
    missing_fields = [field for field in require_fields if field not in config]
    if missing_fields:
        raise KeyError("missing config field: [{0}]".format(",".join(missing_fields)))

    for field in config:
        try:
            if config[field] not in fieldInfos[field]["choices"]:
                raise ValueError("illgeal value: {0} at field: {1}".format(config[field], field))
        except KeyError:
            pass

    unknown_fields = [field for field in config if field not in fieldInfos]
    for field in unknown_fields:
        if field == "command_type":
            continue
        logger.warning("Unknonw Field Name {0}".format(field))


def parse_config(config_field_info):
    cmd_parser = ConfigParserBuilder.setup_cmd_parser(config_field_info)
    cmd_config = cmd_parser.parse_args()

    config_file = cmd_config.config_file
    if not os.path.isfile(config_file):
        config_file = "./application.cfg"

    ini_parser = ConfigParserBuilder.setup_ini_parser()
    ini_parser.read(config_file)

    config = Config(config_field_info, ini_parser, vars(cmd_config))

    verify_config(config_field_info, config)
    return config
