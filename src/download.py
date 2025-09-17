import sys
from lib.download_protocol import DownloadProtocol
from lib.parser import get_parser

def main():
    args = get_parser("download")
    
    if not args.host or not args.port or not args.dst or not args.name:
        print("Usage: python3 download.py -H <host> -p <port> -d <destination> -n <name>")
        sys.exit(1)

    protocol = DownloadProtocol(args)
    success = protocol.download_file()
    if not success:
        print("File download failed.")
        sys.exit(1)

if __name__ == "__main__":
    main()