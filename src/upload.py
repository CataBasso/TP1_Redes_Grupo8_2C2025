import logging
import os
import sys
import time
from lib.upload_protocol import UploadProtocol
from lib.parser import get_parser

def main():
    args = get_parser("upload")
    
    level = logging.INFO
    if args.verbose:
        level = logging.DEBUG
    elif args.quiet:
        level = logging.ERROR
   
    logging.basicConfig(level=level, format='%(asctime)s - %(levelname)s - %(message)s')

    if not args.host or not args.port or not args.src or not args.name:
        logging.error("Usage: python3 upload.py -H <host> -p <port> -s <source> -n <name>")
        sys.exit(1)

    protocol = UploadProtocol(args)
    start_time = time.monotonic()
    upload = protocol.upload_file()
    end_time = time.monotonic()

    if upload:
        duration = end_time - start_time

        logging.info(f"\n--- Transferencia Completa ---")
        logging.info(f"Tiempo total: {duration:.4f} segundos.")
    else:
        logging.error("\nLa transferencia de archivos falló.")
        sys.exit(1)

if __name__ == "__main__":
    main()