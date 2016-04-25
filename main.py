import argparse
from microproxy import proxy
from microproxy.viewer import log as log_viewer


def proxy_handler(args):
        proxy.start_proxy_server(args.host, args.port, args.proxy_mode)


def viewer_handler(args):
    if args.viewer_mode == "log":
        log_viewer.start()


def main():
    parser = argparse.ArgumentParser(description="")
    subparser = parser.add_subparsers()

    proxy_parser = subparser.add_parser('proxy', help="Enable Proxy Server")
    proxy_parser.add_argument("--host", default="127.0.0.1")
    proxy_parser.add_argument("--port", type=int, default=5580)
    proxy_parser.add_argument("--proxy-mode",
                              choices=["socks", "transparent"],
                              default="socks")
    proxy_parser.set_defaults(func=proxy_handler)

    viewer_parser = subparser.add_parser("viewer", help="Open Viewer")
    viewer_parser.add_argument("--viewer-mode",
                               choices=["log"],
                               default="log")
    viewer_parser.set_defaults(func=viewer_handler)

    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
