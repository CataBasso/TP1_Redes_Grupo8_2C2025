import os
import sys
import time
from lib.download_protocol import DownloadProtocol
from lib.parser import get_parser

def main():
    args = get_parser("download")
    
    if not args.host or not args.port or not args.dst or not args.name:
        print("Usage: python3 download.py -H <host> -p <port> -d <destination> -n <name>")
        sys.exit(1)

    protocol = DownloadProtocol(args)
    start_time = time.monotonic()
    download = protocol.download_file()
    end_time = time.monotonic()

    if download:
        duration = end_time - start_time
        
        print(f"\n--- Transferencia Completa ---")
        print(f"Tiempo total: {duration:.4f} segundos.")
    else:
        print("\nLa transferencia de archivos falló.")
        sys.exit(1)


if __name__ == "__main__":
    main()