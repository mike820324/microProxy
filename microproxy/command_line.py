from microproxy.config import parse_config, define_option, define_section


def create_options():

    config_field_info = {}

    proxy_option_info = create_proxy_options()
    define_section(config_field_info=config_field_info,
                   section="proxy",
                   option_info=proxy_option_info,
                   help_str="Open microproxy service")

    console_viewer_option_info = create_console_viewer_options()
    define_section(config_field_info=config_field_info,
                   section="console-viewer",
                   option_info=console_viewer_option_info,
                   help_str="Open console viewer")

    tui_viewer_option_info = create_tui_viewer_options()
    define_section(config_field_info=config_field_info,
                   section="tui-viewer",
                   option_info=tui_viewer_option_info,
                   help_str="Open tui viewer")

    return config_field_info


def create_proxy_options():
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
                  option_name="plugins",
                  help_str="Load plugins",
                  default="",
                  option_type="list",
                  cmd_flags="--plugins",
                  list_type="string")

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

    define_option(option_info=proxy_option_info,
                  option_name="events_channel",
                  help_str="Specify the events channel. ex. tcp://*:5582",
                  option_type="string",
                  default="tcp://127.0.0.1:5582",  # Note: Make default to only accept local to access it
                  cmd_flags="--events-channel")

    return proxy_option_info


def create_tui_viewer_options():
    tui_viewer_option_info = {}

    define_option(option_info=tui_viewer_option_info,
                  option_name="viewer_channel",
                  help_str="Specify the viewer channel. ex. tcp://127.0.0.1:5581",
                  option_type="string",
                  cmd_flags="--viewer-channel")

    define_option(option_info=tui_viewer_option_info,
                  option_name="events_channel",
                  help_str="Specify the events channel. ex. tcp://127.0.0.1:5582",
                  option_type="string",
                  default="tcp://127.0.0.1:5582",
                  cmd_flags="--events-channel")

    define_option(option_info=tui_viewer_option_info,
                  option_name="replay_file",
                  help_str="Specify a replay script file",
                  option_type="string",
                  default="",
                  cmd_flags="--replay-file")
    return tui_viewer_option_info


def create_console_viewer_options():
    console_viewer_option_info = {}

    define_option(option_info=console_viewer_option_info,
                  option_name="proxy_host",
                  help_str="Specify the proxy host. ex. tcp://127.0.0.1",
                  option_type="string",
                  cmd_flags="--proxy-host")

    define_option(option_info=console_viewer_option_info,
                  option_name="viewer_port",
                  help_str="Specify the viewer channel port. ex. 5581",
                  option_type="int",
                  cmd_flags="--viewer-channel-port")

    define_option(option_info=console_viewer_option_info,
                  option_name="events_port",
                  help_str="Specify the events channel port. ex. 5582",
                  option_type="int",
                  cmd_flags="--events-channel-port")

    define_option(option_info=console_viewer_option_info,
                  option_name="verbose_level",
                  help_str="Specify verbose level. (header, body, all)",
                  option_type="string",
                  cmd_flags="--verbose-level",
                  default="status",
                  choices=["status", "header", "body", "all"])

    define_option(option_info=console_viewer_option_info,
                  option_name="replay_file",
                  help_str="Specify replay file",
                  option_type="string",
                  default="",
                  cmd_flags="--replay-file")

    define_option(option_info=console_viewer_option_info,
                  option_name="dump_file",
                  help_str="Specify dump file",
                  option_type="string",
                  default="",
                  cmd_flags="--dump-file")

    return console_viewer_option_info


def main():  # pragma: no cover
    config_field_info = create_options()
    config = parse_config(config_field_info)

    if config["command_type"] == "proxy":
        from microproxy.proxy import start_tcp_server
        from microproxy.event import start_events_server
        from microproxy.utils import get_logger, curr_loop
        from microproxy.cert import init_cert_store
        from microproxy.interceptor import init_interceptor

        logger = get_logger(__name__)
        init_cert_store(config)
        init_interceptor(config)
        start_tcp_server(config)
        start_events_server(config)
        try:
            curr_loop().start()
        except KeyboardInterrupt:
            logger.info("bye")

    elif config["command_type"] == "console-viewer":
        from microproxy.viewer import console as console_viewer
        console_viewer.start(config)

    elif config["command_type"] == "tui-viewer":
        from microproxy.viewer import tui as tui_viewer
        tui_viewer.start(config)


if __name__ == '__main__':
    main()
