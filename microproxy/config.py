import ConfigParser
import argparse

from microproxy.utils import get_logger
logger = get_logger(__name__)


_OPTION_TYPES = ["string", "boolean", "int", "list"]

_LIST_TYPES = ["string", "boolean", "int"]


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

    if option_type not in _OPTION_TYPES:
        raise ValueError("Unsupport type : {0}".format(option_type))

    if choices is not None and not isinstance(choices, list):
        raise ValueError("choices should be a list object")

    option = {
        "help": help_str,
        "type": option_type
    }

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

    if choices:
        option["choices"] = choices

    if option_type == "list":
        if not list_type:
            raise ValueError("Require list_type for option_type list")
        if list_type not in _LIST_TYPES:
            raise ValueError("Unsupport list type : {0}".format(list_type))

        option["list_type"] = list_type

    option_info.update({option_name: option})


def verify_config(config_field_info, config):
    fieldInfos = config_field_info[config["command_type"]]
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
        logger.warning("Unknown field names: {0}".format(",".join(unknown_fields)))


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


def gen_config(config_field_info, file_config, cmd_config):
        command_type = cmd_config["command_type"]
        option_infos = config_field_info[command_type]
        config = dict()

        try:
            file_config = {k.replace(".", "_"): v for k, v in file_config.items(command_type)}
        except:  # pragma: no cover
            pass  # NOTE: No config file found
        else:
            config.update(file_config)

        cmd_config = {k: v for k, v in cmd_config.iteritems() if v is not None and k != "config_file"}
        config.update(cmd_config)

        config.update(append_default(config, option_infos))
        config.update(type_transform(config, option_infos))
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
