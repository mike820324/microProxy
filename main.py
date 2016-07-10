from microproxy.config import parse_config
from microproxy.command_line import create_options


def main():
    config_field_info = create_options()
    config = parse_config(config_field_info)

    if config["command_type"] == "proxy":
        from microproxy import proxy
        proxy.start_proxy_server(config)

    elif config["command_type"] == "console-viewer":
        from microproxy.viewer import console as console_viewer
        console_viewer.start(config)

    elif config["command_type"] == "tui-viewer":
        from microproxy.viewer import tui as tui_viewer
        tui_viewer.start(config)

if __name__ == '__main__':
    main()
