import socket
import sys
import argparse
import os

def argument_parser():
    parser = argparse.ArgumentParser(
        description="<command description>",
        usage="download [-h] [-v | -q] [-H ADDR] [-p PORT] [-d FILEPATH] [-n FILENAME] [-r protocol]"
    )
    verbosity = parser.add_mutually_exclusive_group()
    verbosity.add_argument("-v", "--verbose", action="store_true", help="increase output verbosity")
    verbosity.add_argument("-q", "--quiet", action="store_true", help="decrease output verbosity")
    parser.add_argument("-H", "--host", metavar="", help="server IP address")
    parser.add_argument("-p", "--port", type=int, metavar="", help="server port")
    parser.add_argument("-d", "--dst", metavar="", help="destination file path")
    parser.add_argument("-n", "--name", metavar="", help="file name")
    parser.add_argument("-r", "--protocol", metavar="", help="error recovery protocol")

    parser._optionals.title = "optional arguments"
    return parser.parse_args()

def establish_connection(args):
    download_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # IPv4 y UDP
    download_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    download_socket.settimeout(5)
    
    print(f"Contacting server at {args.host}:{args.port}")
    download_socket.sendto(b"DOWNLOAD_CLIENT", (args.host, args.port))
    
    try:
        data, _ = download_socket.recvfrom(1024)
        if data.decode() != "DOWNLOAD_ACK":
            print("Server did not acknowledge download request.")
            sys.exit(1)
            
        port_data, _ = download_socket.recvfrom(1024)
        if port_data.decode().startswith("PORT:"):
            new_port = int(port_data.decode().split(":")[1])
            print(f"Server assigned new port {new_port} for the download.")
            args.port = new_port
        else:
            print("Did not receive a valid new port from server.")
            sys.exit(1)
            
    except socket.timeout:
        print("No response from server. Exiting.")
        sys.exit(1)
        
    return download_socket

def request_file_info(download_socket, args):
    print(f"Requesting file '{args.name}' from server.")
    download_socket.sendto(args.name.encode(), (args.host, args.port))
    
    try:
        file_info, _ = download_socket.recvfrom(1024)
        info_str = file_info.decode()
        if info_str.startswith("FILESIZE:"):
            filesize = int(info_str.split(":")[1])
            print(f"Server confirmed file exists. Size: {filesize} bytes.")
            download_socket.sendto(b"FILE_INFO_ACK", (args.host, args.port))
            return filesize
        elif info_str == "ERROR:FileNotFound":
            print("Server responded: File not found.")
            sys.exit(1)
        else:
            print(f"Unexpected response from server: {info_str}")
            sys.exit(1)
    except socket.timeout:
        print("No response from server after requesting file info, exiting.")
        sys.exit(1)

def receive_stop_and_wait(args, download_socket, filesize):
    if os.path.isdir(args.dst):
        file_path = os.path.join(args.dst, args.name)
    else:
        file_path = args.dst
    
    print(f"Saving file to: {file_path}")
    
    with open(file_path, "wb") as file:
        seq_expected = 0
        bytes_received = 0
        while bytes_received < filesize:
            try:
                packet, _ = download_socket.recvfrom(4096)
                seq_str, chunk = packet.split(b":", 1)
                seq_received = int(seq_str)
                if seq_received == seq_expected:
                    file.write(chunk)
                    bytes_received += len(chunk)
                    download_socket.sendto(f"ACK:{seq_received}".encode(), (args.host, args.port))
                    
                    seq_expected = 1 - seq_expected
                else:
                    ack_duplicado = 1 - seq_expected
                    print(f"Received duplicate packet {seq_received}, expected {seq_expected}. Resending ACK:{ack_duplicado}")
                    download_socket.sendto(f"ACK:{ack_duplicado}".encode(), (args.host, args.port))
                    
            except socket.timeout:
                print("Timeout waiting for packet. The server might have stopped.")
                break
            except ValueError:
                print("Received a malformed packet. Ignoring.")

    print(f"\nFile '{args.name}' downloaded successfully to '{args.dst}'.")

def recieve_selective_repeat(args, download_socket, filesize):
    """ Implementación del protocolo Selective Repeat para la recepción de archivos
    Ventana deslizante con tamaño fijo, manejo de ACKs individuales y reenvío de paquetes perdidos.
    La función asume que los paquetes tienen el formato "seq_num:chunk" y que el servidor envía
    los paquetes en orden secuencial, pero pueden llegar fuera de orden o perderse.
    La función también maneja la creación del archivo de destino, ya sea en un directorio o con un nombre específico.
    La función utiliza un diccionario para almacenar los paquetes recibidos y sus tiempos de recepción,
    permitiendo reintentos para paquetes que no se confirman dentro de un tiempo límite.

    explicacion paso a paso:
    1. Se determina la ruta completa del archivo de destino, ya sea en un director
    2. Se abre el archivo en modo escritura binaria.
    3. Se inicializan variables para la ventana deslizante, el número base,
    4. Se inicia un bucle que continúa hasta que se hayan recibido todos los bytes del archivo.
    5. Dentro del bucle, se intenta recibir un paquete del servidor.
    6. Se extrae el número de secuencia y el contenido del paquete.
    7. Se verifica si el número de secuencia está dentro de la ventana actual.
       - Si es así, se escribe el contenido en el archivo y se envía un ACK
       - Si no, se ignora el paquete y, si es un paquete antiguo, se reenvía el ACK correspondiente.
    8. Se maneja el caso de timeout y paquetes malformados.
    9. Finalmente, se cierra el archivo y se confirma la descarga exitosa.
    """
    if os.path.isdir(args.dst):
        file_path = os.path.join(args.dst, args.name)
    else:
        file_path = args.dst
    
    print(f"Saving file to: {file_path}")
    
    with open(file_path, "wb") as file:
        window_size = 4 #cant_pkt_env / 2 -> #cant_pkt_env = file_size / channel_size
        base_num = 0
        bytes_sent = 0 
        pkts = {}  # Diccionario: {seq_num: (packet, sent_time)}
        while bytes_sent < filesize:
            try:
                packet, _ = download_socket.recvfrom(4096)
                seq_str, chunk = packet.split(b":", 1)
                seq_received = int(seq_str)
                
                if base_num <= seq_received < base_num + window_size:
                    if seq_received not in pkts:
                        file.write(chunk)
                        bytes_sent += len(chunk)
                        pkts[seq_received] = (packet, None)  
                        print(f"Received and wrote packet {seq_received}.")
                    
                    download_socket.sendto(f"ACK:{seq_received}".encode(), (args.host, args.port))
                    print(f"Sent ACK for packet {seq_received}.")
                    
                    while base_num in pkts:
                        del pkts[base_num]
                        base_num += 1
                else:
                    print(f"Received out-of-window packet {seq_received}, expected window [{base_num}, {base_num + window_size - 1}]. Ignoring.")
                    if seq_received < base_num:
                        download_socket.sendto(f"ACK:{seq_received}".encode(), (args.host, args.port))
                        print(f"Resent ACK for old packet {seq_received}.")
                    
            except socket.timeout:
                print("Timeout waiting for packet. The server might have stopped.")
                break
            except ValueError:
                print("Received a malformed packet. Ignoring.")



def request_file(download_socket, args):
    protocol = args.protocol if args.protocol else "stop-and-wait"
    download_socket.sendto(protocol.encode(), (args.host, args.port))
    
    try:
        ack_data, _ = download_socket.recvfrom(1024)
        if ack_data.decode() != "PROTOCOL_ACK":
            print("Server did not acknowledge protocol choice.")
            sys.exit(1)
    except socket.timeout:
        print("No response from server after sending protocol choice. Exiting.")
        sys.exit(1)

    filesize = request_file_info(download_socket, args)
    
    if protocol == "stop-and-wait":
        receive_stop_and_wait(args, download_socket, filesize)
    elif protocol == "selective-repeat":
        recieve_selective_repeat(args, download_socket, filesize)


def main():
    args = argument_parser()
    download_socket = establish_connection(args)
    request_file(download_socket, args)
    download_socket.close()

if __name__ == "__main__":
    main()