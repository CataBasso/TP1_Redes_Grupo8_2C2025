import socket
import sys
import argparse
import threading
import os
from lib.srv_protocol import ServerProtocol

BUFFER = 1024
ERROR = 1


def argument_parser():
    parser = argparse.ArgumentParser(
        description="<command description>",
        usage="start -server [-h] [-v | -q] [-H ADDR] [-p PORT] [-s DIRPATH]",
    )
    verbosity = parser.add_mutually_exclusive_group()
    verbosity.add_argument(
        "-v", "--verbose", action="store_true", help="increase output verbosity"
    )
    verbosity.add_argument(
        "-q", "--quiet", action="store_true", help="decrease output verbosity"
    )
    parser.add_argument("-H", "--host", metavar="", help="service IP address")
    parser.add_argument("-p", "--port", metavar="", type=int, help="service port")
    parser.add_argument("-s", "--storage", metavar="", help="storage dir path")

    parser._optionals.title = "optional arguments"
    return parser.parse_args()


def handle_client(protocol: ServerProtocol, addr, data):
    protocol.handle_client(addr, data)


def main():
    args = argument_parser()

    if not args.host or not args.port:
        print("Usage: python3 start-server.py -H <host> -p <port>")
        sys.exit(ERROR)

    # AF_INET for IPv4, SOCK_DGRAM for UDP
    # SOL_SOCKET to set socket options, SO_REUSEADDR to reuse the address
    skt = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    skt.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    skt.bind((args.host, args.port))
    print(f"Server listening on {args.host}:{args.port}")

    threads = {}
    protocol = ServerProtocol(skt, args)

    try:
        while True:
            data, addr = skt.recvfrom(BUFFER)
            if addr not in threads:
                thread = threading.Thread(
                    target=handle_client, args=(protocol, addr, data)
                )
                threads[addr] = thread
                thread.start()
    except KeyboardInterrupt:
        print("Server shutting down.")
    finally:
        for thread in threads.values():
            thread.join()
        skt.close()


if __name__ == "__main__":
    main()
