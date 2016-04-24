import argparse
from microproxy import proxy
from microproxy.viewer import log as log_viewer


def main():
    parser = argparse.ArgumentParser(description="")
    parser.add_argument("service", help="define which service to start: proxy,sub")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5580)
    parser.add_argument("--viewer_type", default="log")
    args = parser.parse_args()
    if args.service == "proxy":
        proxy.start_proxy_server(args.host, args.port)

    if args.service == "viewer":
        if args.viewer_type == "log":
            log_viewer.start()

if __name__ == "__main__":
    main()
