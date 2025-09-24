import logging
import socket
import sys
import threading
import select

from lib.srv_protocol import ServerProtocol
from lib.parser import get_parser

BUFFER = 4064
ERROR = 1

def handle_client(protocol: ServerProtocol, addr, data):
    protocol.handle_client(addr, data)

def check_quit_input():
    """Verifica si hay input disponible sin bloquear"""
    if select.select([sys.stdin], [], [], 0) == ([sys.stdin], [], []):
        user_input = sys.stdin.readline().strip().lower()
        if user_input == 'q':
            return True
    return False

def main():
    args = get_parser("server")
    level = logging.INFO
    if args.verbose:
        level = logging.DEBUG
    elif args.quiet:
        level = logging.ERROR
   
    logging.basicConfig(level=level, format='%(asctime)s - %(levelname)s - %(message)s')

    if not args.host or not args.port:
        logging.error("Usage: python3 start-server.py -H <host> -p <port>")
        sys.exit(ERROR)

    # AF_INET for IPv4, SOCK_DGRAM for UDP
    # SOL_SOCKET to set socket options, SO_REUSEADDR to reuse the address
    skt = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    skt.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    skt.bind((args.host, args.port))
    logging.info(f"SERVIDOR-MAIN Escuchando: {args.host}:{args.port}")
    print("Ingresa 'q' y Enter para cerrar el servidor.")
    
    protocol = ServerProtocol(args)
    protocol.set_main_socket(skt)

    active_threads = []
    
    try:
        while True:
            if check_quit_input():
                logging.info("Cerrando servidor...")
                break

            skt.settimeout(1.0)
            
            try:
                data, addr = skt.recvfrom(BUFFER)
                message = data.decode()
                parts = message.split(':', 4) 

                # Validamos que sea un saludo de UPLOAD correcto
                if len(parts) == 4 and parts[0] == 'UPLOAD_CLIENT':
                    # Formato: "UPLOAD_CLIENT:protocol:filename:filesize"
                    logging.info(f"SERVIDOR-MAIN: Saludo de UPLOAD recibido de {addr}")
                    thread = threading.Thread(
                        target=protocol.handle_upload,
                        args=(addr, parts[1], parts[2], int(parts[3]))
                    )
                    thread.start()
                    active_threads.append(thread)
                # Validamos que sea un saludo de DOWNLOAD correcto
                elif len(parts) == 3 and parts[0] == 'DOWNLOAD_CLIENT':
                    # Formato: "DOWNLOAD_CLIENT:protocol:filename"
                    logging.info(f"SERVIDOR-MAIN: Saludo de DOWNLOAD recibido de {addr}")
                    thread = threading.Thread(
                        target=protocol.handle_download,
                        args=(addr, parts[1], parts[2])
                    )
                    thread.start()
                    active_threads.append(thread)
                else:
                    logging.warning(f"SERVIDOR-MAIN: Paquete de saludo inválido de {addr}. Ignorando.")

            except socket.timeout:
                active_threads = [t for t in active_threads if t.is_alive()]
                continue
            except (UnicodeDecodeError, ValueError) as e:
                logging.error(f"SERVIDOR-MAIN: Paquete corrupto de {addr}:{e}. Ignorando.")
        
    except KeyboardInterrupt:
        logging.info("Cerrando servidor por KeyboardInterrupt...")
    
    logging.info("Cerrando conexiones...")
    skt.close()
    if active_threads:
        active_count = len([t for t in active_threads if t.is_alive()])
        if active_count > 0:
            logging.info(f"Esperando {active_count} transferencias activas...")
            
            for thread in active_threads:
                if thread.is_alive():
                    thread.join(timeout=3.0)
    
    logging.info("Servidor cerrado correctamente.")

if __name__ == "__main__":
    main()
