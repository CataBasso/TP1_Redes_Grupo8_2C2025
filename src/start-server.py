import sys
import threading
from lib.srv_protocol import ServerProtocol
from lib.parser import get_parser
from lib.socket import Socket

BUFFER = 1024
ERROR = 1

def established(protocol: ServerProtocol, client_socket):
    protocol.handle_request(client_socket)


def main():
    args = get_parser("server")

    if not args.host or not args.port:
        print("Usage: python3 start-server.py -H <host> -p <port>")
        sys.exit(ERROR)

    skt = Socket(args.host,args.port)
    print(f"Server listening on {args.host}:{args.port}")

    threads = {}
    protocol = ServerProtocol(args)

    try:
        while True:
            client_socket ,port = skt.accept()
            if not client_socket:
                continue

            thread = threading.Thread(
                target=established, args=(protocol, client_socket)
            )
            thread.start()
            threads[port] = thread
    except KeyboardInterrupt:
        print("Server shutting down.")
    finally:
        for thread in threads.values():
            thread.join()
        skt.close()


if __name__ == "__main__":
    main()
