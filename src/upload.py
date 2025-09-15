import socket
import sys
import argparse

def main():
    parser = argparse.ArgumentParser(
        description="<command description>",
        usage="upload [-h] [-v | -q] [-H ADDR] [-p PORT] [-s FILEPATH] [-n FILENAME] [-r protocol]"
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

    # esto en realidad seria:
    # if not args.host or not args.port or not args.src or not args.name:
    #   print("Usage: python3 upload.py -H <host> -p <port> -s <source> -n <name>")
    #   sys.exit(1)
    # pero por ahora lo dejamos asi para probar la comunicacion
    if not args.host or not args.port:
        print("Usage: python3 upload.py -H <host> -p <port>")
        sys.exit(1)

    upload_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    upload_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    print(f"Connected to server at {args.host}:{args.port}")

    while True:
        message = input("Enter message to send (or 'exit' to quit): ")
        upload_socket.sendto(message.encode(), (args.host, args.port))

        if message == "exit":
            print("Exiting client.")
            break

        data = upload_socket.recvfrom(1024)
        print(f"Received from server: {data.decode()}")

    upload_socket.close()

if __name__ == "__main__":
    main()