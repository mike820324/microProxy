import argparse
import proxy
import connection_controller

def main():
    parser = argparse.ArgumentParser(description="")
    parser.add_argument("service", help="define which service to start: proxy,cc")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5580)
    args = parser.parse_args()
    if args.service == "proxy":
        proxy.start_proxy_server(args.host, args.port)
    if args.service == "cc":
        connection_controller.start_server()

if __name__ == "__main__":
    main()
