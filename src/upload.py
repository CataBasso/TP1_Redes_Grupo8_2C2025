import socket
import sys
import argparse

def main():
    parser = argparse.ArgumentParser(
        description="<comand description>"
    )
    verbosity = parser.add_mutually_exclusive_group()
    verbosity.add_argument("-v", "--verbose", action="store_true", help="increase output verbosity")
    verbosity.add_argument("-q", "--quiet", action="store_true", help="decrease output verbosity")
    parser.add_argument("-H", "--host", metavar="", help="server IP address")
    parser.add_argument("-p", "--port", type=int, metavar="", help="server port")
    parser.add_argument("-s", "--src", metavar="", help="source file path")
    parser.add_argument("-n", "--name", metavar="", help="file name")
    parser.add_argument("-r", "--protocol", metavar="", help="error recovery protocol")

    parser._optionals.title = "optional arguments"
    args = parser.parse_args()

    if not args.host or not args.port:
        print("Usage: python3 upload.py -H <host> -p <port>")
        sys.exit(1)

    client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    client_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    client_socket.connect((args.host, args.port))
    print(f"Connected to server at {args.host}:{args.port}")

    while True:
        message = input("Enter message to send (or 'exit' to quit): ")
        client_socket.sendto(message.encode(), (args.host, args.port))

        if message == "exit":
            print("Exiting client.")
            break

        data, addr = client_socket.recvfrom(1024)
        print(f"Received from server: {data.decode()}")

    client_socket.close()

if __name__ == "__main__":
    main()