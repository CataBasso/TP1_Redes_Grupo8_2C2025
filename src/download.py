import os
import sys
import time
from lib.download_protocol import DownloadProtocol
from lib.parser import get_parser
from lib.logger import init_logger, get_logger

def main():
    args = get_parser("download")
    
    # Initialize logger with verbosity settings
    logger = init_logger(verbose=args.verbose, quiet=args.quiet)
    
    if not args.host or not args.port or not args.dst or not args.name:
        logger.error("Usage: python3 download.py -H <host> -p <port> -d <destination> -n <name>")
        sys.exit(1)

    protocol = DownloadProtocol(args)
    start_time = time.monotonic()
    download = protocol.download_file()
    end_time = time.monotonic()

    if download:
        duration = end_time - start_time
        logger.info("File transfer completed successfully")
        logger.info(f"Total transfer time: {duration:.4f} seconds")
        logger.debug(f"File: {args.name} -> {args.dst}")
    else:
        logger.error("File transfer failed")
        sys.exit(1)


if __name__ == "__main__":
    main()