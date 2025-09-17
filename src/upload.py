import sys
from lib.upload_protocol import UploadProtocol
from lib.parser import get_parser

def main():
    args = get_parser("upload")

    if not args.host or not args.port or not args.src or not args.name:
        print("Usage: python3 upload.py -H <host> -p <port> -s <source> -n <name>")
        sys.exit(1)

    protocol = UploadProtocol(args)
    upload = protocol.upload_file()
    if not upload:
        print("File upload failed.")
        sys.exit(1)

if __name__ == "__main__":
    main()