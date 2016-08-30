from microproxy.config import parse_config
from microproxy.command_line import create_options


def main():
    config_field_info = create_options()
    config = parse_config(config_field_info)

    if config["command_type"] == "proxy":
        from microproxy.proxy import start_tcp_server
        from microproxy.event import start_events_server
        from microproxy.utils import get_logger, curr_loop

        logger = get_logger(__name__)

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
