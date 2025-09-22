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
            parts = message.split(':', 3) # Dividir en máximo 4 partes

            # Validamos que sea un saludo de UPLOAD correcto
            if len(parts) == 4 and parts[0] == 'UPLOAD_CLIENT': # Asumiendo que usas UPLOAD_CLIENT
                print(f"SERVIDOR-MAIN: Saludo de UPLOAD recibido de {addr}")
                # Pasamos toda la info al hilo
                thread = threading.Thread(
                    target=protocol.handle_upload,
                    args=(addr, parts[1], parts[2], int(parts[3]))
                )
                thread.start()
            else:
                print(f"SERVIDOR-MAIN: Paquete de saludo inválido de {addr}. Ignorando.")

        except (UnicodeDecodeError, ValueError):
            print(f"SERVIDOR-MAIN: Paquete corrupto de {addr}. Ignorando.")
    # try:
    #     while True:
    #         data, addr = skt.recvfrom(BUFFER)
    #         message = data.decode()

    #         if message == "UPLOAD_CLIENT" or message == "DOWNLOAD_CLIENT":
    #             print(f"\nSERVIDOR-MAIN: Petición '{message}' recibida de {addr}, iniciando hilo...")
    #             thread = threading.Thread(
    #                 target=handle_client, args=(protocol, addr, data)
    #             )
    #             thread.start()
    #         else:
    #             print(f"\nSERVIDOR-MAIN: Paquete inesperado de {addr} en puerto principal (contenido: '{message}'). Ignorando.")
    # except KeyboardInterrupt:
    #     print("Server shutting down.")
    # finally:
    #     for thread in threads.values():
    #         thread.join()
    #     skt.close()


if __name__ == "__main__":
    main()
