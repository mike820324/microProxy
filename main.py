from microproxy import proxy
from microproxy.viewer import log as log_viewer
from microproxy.config import parse_config


if __name__ == "__main__":
    config = parse_config()
    if config is None:
        exit(0)

    if config["command_type"] == "proxy":
        proxy.start_proxy_server(config)

    elif config["command_type"] == "viewer":
        log_viewer.start(config)
