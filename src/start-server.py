import socket
import sys
import threading
from lib.srv_protocol import ServerProtocol
from lib.parser import get_parser

BUFFER = 4064
ERROR = 1

def handle_client(protocol: ServerProtocol, addr, data):
    protocol.handle_client(addr, data)


def main():
    args = get_parser("server")

    if not args.host or not args.port:
        print("Usage: python3 start-server.py -H <host> -p <port>")
        sys.exit(ERROR)

    # AF_INET for IPv4, SOCK_DGRAM for UDP
    # SOL_SOCKET to set socket options, SO_REUSEADDR to reuse the address
    skt = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    skt.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    skt.bind((args.host, args.port))
    print(f"Server listening on {args.host}:{args.port}")

    threads = {}
    protocol = ServerProtocol(args)
    while True:
        data, addr = skt.recvfrom(BUFFER)
        try:
            message = data.decode()
            parts = message.split(':', 4) 

            # Validamos que sea un saludo de UPLOAD correcto
            if len(parts) == 4 and parts[0] == 'UPLOAD_CLIENT':
                # Formato: "UPLOAD_CLIENT:protocol:filename:filesize"
                print(f"SERVIDOR-MAIN: Saludo de UPLOAD recibido de {addr}")
                thread = threading.Thread(
                    target=protocol.handle_upload,
                    args=(addr, parts[1], parts[2], int(parts[3]))
                )
                thread.start()
            elif len(parts) == 3 and parts[0] == 'DOWNLOAD_CLIENT':
                # Formato: "DOWNLOAD_CLIENT:protocol:filename"
                print(f"SERVIDOR-MAIN: Saludo de DOWNLOAD recibido de {addr}")
                thread = threading.Thread(
                    target=protocol.handle_download,
                    args=(addr, parts[1], parts[2])
                )
                thread.start()
            else:
                print(f"SERVIDOR-MAIN: Paquete de saludo inválido de {addr}. Ignorando.")

        except (UnicodeDecodeError, ValueError) as e:
            print(f"SERVIDOR-MAIN: Paquete corrupto de {addr}:{e}. Ignorando.")
    
    # except KeyboardInterrupt:
    #     print("Server shutting down.")
    # finally:
    #    for thread in threading.enumerate():
    #        if thread != threading.current_thread():
    #            thread.join(timeout=1.0)
    #    skt.close()


if __name__ == "__main__":
    main()
