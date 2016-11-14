import ConfigParser
import argparse

from microproxy.log import ProxyLogger


_OPTION_TYPES = ["str", "bool", "int", "list:str", "list:int"]


class ConfigParserBuilder(object):
    @staticmethod
    def setup_ini_parser():
        parser = ConfigParser.SafeConfigParser()
        return parser

    @staticmethod
    def setup_cmd_parser(config_field_info):
        parser = argparse.ArgumentParser(description="MicroProxy a http/https proxy interceptor.")

        parser.add_argument("--config-file",
                            default="",
                            help="Specify config file location")

        for field_name, field_info in config_field_info.iteritems():
            if "bool" == field_info["type"]:
                parser.add_argument(*field_info["cmd_flags"],
                                    dest=field_name,
                                    action="store_true",
                                    help=field_info["help"])
            else:
                parser.add_argument(*field_info["cmd_flags"],
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
                  config_file_flags=None,
                  choices=None
                  ):
    if not isinstance(option_info, dict):
        raise ValueError("Expect option_info as a dictionary")

    if not config_file_flags and not cmd_flags:
        raise ValueError("Useless option")

    if option_name in option_info:
        raise ValueError("option {} is already defined".format(option_name))

    if option_type not in _OPTION_TYPES:
        raise ValueError("Unsupport type : {0}".format(option_type))

    if choices is not None:
        if not isinstance(choices, list):
            raise ValueError("choices should be a list object")

        if default is not None and default not in choices:
            raise ValueError("default value {0} not in {1}".format(default, choices))

    option = {
        "help": help_str,
        "type": option_type
    }

    if choices:
        option["choices"] = choices

    if default is not None:
        option["is_require"] = False
        option["default"] = default
    else:
        option["is_require"] = True

    if cmd_flags:
        if isinstance(cmd_flags, str):
            option["cmd_flags"] = [cmd_flags]
        elif isinstance(cmd_flags, list):
            option["cmd_flags"] = cmd_flags

    if config_file_flags:
        option["config_file_flags"] = {
            "section": config_file_flags.split(":")[0],
            "key": config_file_flags.split(":")[1]
        }

    option_info.update({option_name: option})


def verify_config(config_field_info, config):
    fieldInfos = config_field_info
    require_fields = [k for k, v in fieldInfos.iteritems() if v["is_require"]]
    missing_fields = [field for field in require_fields if field not in config]
    if missing_fields:
        raise KeyError("missing config field: [{0}]".format(",".join(missing_fields)))

    # NOTE: Verify that the value in choices
    for field in config:
        try:
            if config[field] not in fieldInfos[field]["choices"]:
                raise ValueError("illgeal value: {0} at field: {1}".format(config[field], field))
        except KeyError:
            pass

    unknown_fields = [field for field in config if field not in fieldInfos]
    if unknown_fields:
        ProxyLogger.get_logger(__name__).warning(
            "Unknown field names: {0}".format(",".join(unknown_fields)))


def parse_config(config_field_info, args=None):  # pragma: no cover
    cmd_parser = ConfigParserBuilder.setup_cmd_parser(config_field_info)
    if args:
        cmd_config = cmd_parser.parse_args(args)
    else:
        cmd_config = cmd_parser.parse_args()

    ini_parser = ConfigParserBuilder.setup_ini_parser()
    ini_parser.read([cmd_config.config_file, "application.cfg"])

    config = gen_config(config_field_info, ini_parser, vars(cmd_config))

    verify_config(config_field_info, config)
    return config


def gen_file_config(config_field_info, file_config):
    config = dict()
    for field_name, field_info in config_field_info.iteritems():
        try:
            section = field_info["config_file_flags"]["section"]
            key = field_info["config_file_flags"]["key"]
            config[field_name] = file_config.get(section, key)
        except (KeyError, ConfigParser.NoSectionError, ConfigParser.NoOptionError):
            continue

    return config


def gen_config(config_field_info, file_config, cmd_config):
        config = dict()

        config.update(gen_file_config(config_field_info, file_config))

        cmd_config = {k: v for k, v in cmd_config.iteritems() if v is not None and k != "config_file"}
        config.update(cmd_config)

        config.update(append_default(config, config_field_info))
        config.update(type_transform(config, config_field_info))
        return config


def append_default(config, optionInfo):
    fields = [field for field in optionInfo if field not in config and not optionInfo[field]["is_require"]]
    options = {field: optionInfo[field]["default"] for field in fields}
    return options


def type_transform(config, optionInfo):
    new_config = {}
    for field in config:
        if field not in optionInfo:
            continue
        option_type = optionInfo[field]["type"]

        if "str" == option_type or "bool" == option_type:
            new_config[field] = config[field]
        elif "int" == option_type:
            new_config[field] = int(config[field])
        elif "list:str" == option_type:
            values = [value for value in config[field].split(",") if len(value) > 0]
            new_config[field] = values
        elif "list:int" == option_type:
            values = [value for value in config[field].split(",") if len(value) > 0]
            new_config[field] = map(int, values)
        else:
            raise ValueError("Non supported type")

    return new_config
