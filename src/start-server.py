import socket
import sys
import threading
from lib.srv_protocol import ServerProtocol
from lib.parser import get_parser

BUFFER = 1024
ERROR = 1

def handle_client(protocol: ServerProtocol, addr, data):
    protocol.handle_client(addr, data)


def main():
    args = get_parser("server")

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
    protocol = ServerProtocol(args)

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
