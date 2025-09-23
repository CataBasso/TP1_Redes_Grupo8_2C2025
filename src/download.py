import os
import sys
import time
import logging
from lib.download_protocol import DownloadProtocol
from lib.parser import get_parser

def main():
    args = get_parser("download")
       
    level = logging.INFO
    if args.verbose:
        level = logging.DEBUG
    elif args.quiet:
        level = logging.ERROR
   
    logging.basicConfig(level=level, format='%(asctime)s - %(levelname)s - %(message)s')

    if not args.host or not args.port or not args.dst or not args.name:
        logging.error("Usage: python3 download.py -H <host> -p <port> -d <destination> -n <name>")
        sys.exit(1)

    protocol = DownloadProtocol(args)
    start_time = time.monotonic()
    download = protocol.download_file()
    end_time = time.monotonic()

    if download:
        duration = end_time - start_time

        logging.info(f"\n--- Transferencia Completa ---")
        logging.info(f"Tiempo total: {duration:.4f} segundos.")
    else:
        logging.error("\nLa transferencia de archivos falló.")
        sys.exit(1)


if __name__ == "__main__":
    main()