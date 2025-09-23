import os
import sys
import time
from lib.upload_protocol import UploadProtocol
from lib.parser import get_parser
from lib.logger import init_logger, get_logger

def main():
    args = get_parser("upload")
    
    # Initialize logger with verbosity settings
    logger = init_logger(verbose=args.verbose, quiet=args.quiet)

    if not args.host or not args.port or not args.src or not args.name:
        logger.error("Usage: python3 upload.py -H <host> -p <port> -s <source> -n <name>")
        sys.exit(1)

    protocol = UploadProtocol(args)
    start_time = time.monotonic()
    upload = protocol.upload_file()
    end_time = time.monotonic()

    if upload:
        duration = end_time - start_time
        logger.info("File transfer completed successfully")
        logger.info(f"Total transfer time: {duration:.4f} seconds")
        logger.debug(f"File: {args.src} -> {args.name}")
    else:
        logger.error("File transfer failed")
        sys.exit(1)

if __name__ == "__main__":
    main()