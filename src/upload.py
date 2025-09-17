import socket
import sys
import argparse
from lib.upload_protocol import UploadProtocol

def argument_parser():
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
    return parser.parse_args()
    
def main():
    args = argument_parser()

    if not args.host or not args.port or not args.src or not args.name:
        print("Usage: python3 upload.py -H <host> -p <port> -s <source> -n <name>")
        sys.exit(1)
    
    upload_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    upload_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    protocol = UploadProtocol(upload_socket, args)

    upload = protocol.upload_file()
    if not upload:
        print("File upload failed.")
        upload_socket.close()
        sys.exit(1)
    
    upload_socket.close()
    sys.exit(0)

if __name__ == "__main__":
    main()