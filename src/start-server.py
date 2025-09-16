import socket
import sys
import argparse
import threading
import os

def argument_parser():
    parser = argparse.ArgumentParser(
        description="<command description>",
        usage="start -server [-h] [-v | -q] [-H ADDR] [-p PORT] [-s DIRPATH]"
    )
    verbosity = parser.add_mutually_exclusive_group()
    verbosity.add_argument("-v", "--verbose", action="store_true", help="increase output verbosity")
    verbosity.add_argument("-q", "--quiet", action="store_true", help="decrease output verbosity")
    parser.add_argument("-H", "--host", metavar="", help="service IP address")
    parser.add_argument("-p", "--port", metavar="", type=int, help="service port")
    parser.add_argument("-s", "--storage", metavar="", help="storage dir path")

    parser._optionals.title = "optional arguments"
    return parser.parse_args()

def handle_client(server_socket, addr, data):
    if not data or data.decode() == "exit":
        print(f"Client {addr} disconnected.")
        return
    
    print(f"Received message: {data.decode()} from {addr}")
    server_socket.sendto(b"ACK", addr)

def main():
    args = argument_parser()

    if not args.host or not args.port:
        print("Usage: python3 start-server.py <host> <port>")
        sys.exit(1)

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((args.host, args.port))
    print(f"Server listening on {args.host}:{args.port}")

    try:
        while True:
            data, addr = server_socket.recvfrom(1024)
            client_thread = threading.Thread(
                target=handle_client,
                args=(server_socket, addr, data)
            )
            client_thread.start()
    except KeyboardInterrupt:
        print("Server shutting down.")
    finally:
        server_socket.close()

if __name__ == "__main__":
    main()