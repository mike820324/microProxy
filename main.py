from microproxy import proxy
from microproxy.viewer import log as log_viewer
from microproxy.config import parse_config, define_option, define_section


def create_options():
    proxy_option_info = {}
    define_option(option_info=proxy_option_info,
                  option_name="host",
                  help_str="Specify the proxy host",
                  default="127.0.0.1",
                  option_type="string",
                  cmd_flags="--host")

    define_option(option_info=proxy_option_info,
                  option_name="port",
                  help_str="Specify the proxy listening port",
                  default="5580",
                  option_type="int",
                  cmd_flags="--port")

    define_option(option_info=proxy_option_info,
                  option_name="mode",
                  help_str="Speficy the proxy mode, currently support socks proxy and transparent proxy",
                  option_type="string",
                  cmd_flags="--mode",
                  choices=["socks", "transparent"])

    define_option(option_info=proxy_option_info,
                  option_name="http_port",
                  help_str="Add additional http port",
                  default="",
                  option_type="list",
                  cmd_flags="--http-port",
                  list_type="int")

    define_option(option_info=proxy_option_info,
                  option_name="https_port",
                  help_str="Add additional https port",
                  default="",
                  option_type="list",
                  cmd_flags="--https-port",
                  list_type="int")

    define_option(option_info=proxy_option_info,
                  option_name="viewer_channel",
                  help_str="Specify the viewer channel. ex. tcp://*:5581",
                  option_type="string",
                  cmd_flags="--viewer-channel")

    define_option(option_info=proxy_option_info,
                  option_name="certfile",
                  help_str="Specify the certificate file",
                  option_type="string",
                  cmd_flags="--cert-file")

    define_option(option_info=proxy_option_info,
                  option_name="keyfile",
                  help_str="Specify the private key file",
                  option_type="string",
                  cmd_flags="--key-file")

    viewer_option_info = {}
    define_option(option_info=viewer_option_info,
                  option_name="mode",
                  help_str="Specify the viewer type",
                  option_type="string",
                  cmd_flags="--mode",
                  choices=["--mode"])

    define_option(option_info=viewer_option_info,
                  option_name="viewer_channel",
                  help_str="Specify the viewer channel",
                  option_type="string",
                  cmd_flags="--viewer-channel")

    config_field_info = {}
    define_section(config_field_info=config_field_info,
                   section="proxy",
                   option_info=proxy_option_info,
                   help_str="Open microproxy service")
    define_section(config_field_info=config_field_info,
                   section="viewer",
                   option_info=viewer_option_info,
                   help_str="Open viewer")

    return config_field_info

if __name__ == "__main__":
    config_field_info = create_options()
    config = parse_config(config_field_info)

    if config["command_type"] == "proxy":
        proxy.start_proxy_server(config)

    elif config["command_type"] == "viewer":
        log_viewer.start(config)
