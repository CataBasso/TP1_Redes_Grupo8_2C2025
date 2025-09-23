import socket
import sys
import threading
from lib.srv_protocol import ServerProtocol
from lib.parser import get_parser
from lib.logger import init_logger, get_logger

BUFFER = 4064
ERROR = 1

def handle_client(protocol: ServerProtocol, addr, data):
    protocol.handle_client(addr, data)

def main():
    args = get_parser("server")
    
    # Initialize logger with verbosity settings
    logger = init_logger(verbose=args.verbose, quiet=args.quiet)

    if not args.host or not args.port:
        logger.error("Usage: python3 start-server.py -H <host> -p <port>")
        sys.exit(ERROR)

    # AF_INET for IPv4, SOCK_DGRAM for UDP
    # SOL_SOCKET to set socket options, SO_REUSEADDR to reuse the address
    skt = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    skt.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    skt.bind((args.host, args.port))
    logger.info(f"Server listening on {args.host}:{args.port}")
    logger.debug(f"Server storage directory: {args.storage or 'default'}")

    protocol = ServerProtocol(args)
    protocol.set_main_socket(skt)
    
    while True:
        logger.verbose_info("Waiting for client connections...")
        data, addr = skt.recvfrom(BUFFER)
        logger.debug(f"Received data from {addr}: {data[:50]}...")
        try:
            message = data.decode()
            parts = message.split(':', 4) 

            # Validamos que sea un saludo de UPLOAD correcto
            if len(parts) == 4 and parts[0] == 'UPLOAD_CLIENT':
                # Formato: "UPLOAD_CLIENT:protocol:filename:filesize"
                logger.info(f"UPLOAD request received from {addr}")
                logger.debug(f"Upload details - Protocol: {parts[1]}, Filename: {parts[2]}, Size: {parts[3]}")
                thread = threading.Thread(
                    target=protocol.handle_upload,
                    args=(addr, parts[1], parts[2], int(parts[3]))
                )
                thread.start()
            # Validamos que sea un saludo de DOWNLOAD correcto
            elif len(parts) == 3 and parts[0] == 'DOWNLOAD_CLIENT':
                # Formato: "DOWNLOAD_CLIENT:protocol:filename"
                logger.info(f"DOWNLOAD request received from {addr}")
                logger.debug(f"Download details - Protocol: {parts[1]}, Filename: {parts[2]}")
                thread = threading.Thread(
                    target=protocol.handle_download,
                    args=(addr, parts[1], parts[2])
                )
                thread.start()
            else:
                logger.error(f"Invalid handshake packet from {addr}. Ignoring.")

        except (UnicodeDecodeError, ValueError) as e:
            logger.error(f"Corrupted packet from {addr}: {e}. Ignoring.")
    
    # except KeyboardInterrupt:
    #     print("Server shutting down.")
    # finally:
    #    for thread in threading.enumerate():
    #        if thread != threading.current_thread():
    #            thread.join(timeout=1.0)
    #    skt.close()


if __name__ == "__main__":
    main()
