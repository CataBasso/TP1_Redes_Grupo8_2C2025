import socket
import sys
import argparse
import threading
import os


def argument_parser():
    parser = argparse.ArgumentParser(
        description="<command description>",
        usage="start -server [-h] [-v | -q] [-H ADDR] [-p PORT] [-s DIRPATH]",
    )
    verbosity = parser.add_mutually_exclusive_group()
    verbosity.add_argument(
        "-v", "--verbose", action="store_true", help="increase output verbosity"
    )
    verbosity.add_argument(
        "-q", "--quiet", action="store_true", help="decrease output verbosity"
    )
    parser.add_argument("-H", "--host", metavar="", help="service IP address")
    parser.add_argument("-p", "--port", metavar="", type=int, help="service port")
    parser.add_argument("-s", "--storage", metavar="", help="storage dir path")

    parser._optionals.title = "optional arguments"
    return parser.parse_args()


def recieve_selective_repeat(client_socket, addr, filesize, file_path):
    #lo que tengo que hacer basicamente es 
    #recibir paquetes, ver si estan en orden,
    # si el paquete recibido está en orden, envio un ack
    # si el paquete recibido no está en orden, lo buffereo
    # cuando buffereo envio el ack del que recibi
    # en algun momento voy a volver a recibir el paquete perdido, una vez q lo recibi, saco todo del buffer
    # y envio el ack del paquete recibido
    seq_expected = 0
    bytes_received = 0
    buffer = []
    while bytes_received < filesize: 
        packet, saddr = client_socket.recvfrom(4096)
        try:
            seq_str, chunk = packet.split(b":", 1)
            seq_received = int(seq_str)
        except Exception:
            print(f"Packet format error from {addr}, ignoring.")
            continue
        if seq_received == seq_expected:
            print("rec == expected")
            bytes_received += len(chunk)
            print(f"delivered: {seq_expected}")
            if len(buffer) > 0 :
                seq_expected += 1
                #deliver pkts in buffer, basicamente me permite ir hasta el proximo paquete perdido
                #te envio hasta el proximo paquete que se haya perdido
                #voy aumentando el expected hasta llegar al elemento del buffer que no este en orden ahi dejo de hacer pop                
                for i in buffer:
                    if seq_expected == i[0]:
                        print(f"delivered: {seq_expected}")
                        seq_expected += 1 #se supone que en la primera posicion me quedo el ACK del último recibido válido
                    else: 
                        print("have in buffer another packet loss")
            client_socket.sendto(f"ACK:{seq_received}".encode(), addr)
        else:
            print("rec != expected: queued")
            buffer.append((seq_received,chunk))
            client_socket.sendto(f"ACK:{seq_received}".encode(), addr)
            


def recieve_stop_and_wait(client_socket, addr, filesize, file_path):
    with open(file_path, "wb") as recieved_file:
        seq_expected = 0
        bytes_received = 0
        while bytes_received < filesize:
            packet, saddr = client_socket.recvfrom(4096)
            if packet == b"EOF":
                break
            try:
                seq_str, chunk = packet.split(b":", 1)
                seq_received = int(seq_str)
            except Exception:
                print(f"Packet format error from {addr}, ignoring.")
                continue

            if seq_received == seq_expected:
                recieved_file.write(chunk)
                bytes_received += len(chunk)
                client_socket.sendto(f"ACK:{seq_received}".encode(), addr)
                seq_expected = 1 - seq_expected
            else:
                client_socket.sendto(f"ACK:{1 - seq_expected}".encode(), addr)

        if bytes_received >= filesize:
            eof, saddr = client_socket.recvfrom(1024)


def handle_upload(addr, args):
    print(f"Client {addr} connected for upload.")

    client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    client_socket.bind(("", 0))
    client_port = client_socket.getsockname()[1]

    client_socket.sendto(b"UPLOAD_ACK", addr)
    client_socket.sendto(f"PORT:{client_port}".encode(), addr)
    client_socket.settimeout(10)

    try:
        protocol_data, _ = client_socket.recvfrom(1024)
        protocol = protocol_data.decode()
        print(f"Client using protocol: {protocol}")
        client_socket.sendto(b"PROTOCOL_ACK", addr)

        file_info, saddr = client_socket.recvfrom(1024)
        filename, filesize = file_info.decode().split(":")
        filesize = int(filesize)
        print(f"Receiving file {filename} of size {filesize} bytes from {addr}")
        client_socket.sendto(b"FILE_INFO_ACK", addr)

        storage_path = args.storage if args.storage else "storage"
        os.makedirs(storage_path, exist_ok=True)
        file_path = os.path.join(storage_path, filename)

        if protocol == "stop-and-wait":
            recieve_stop_and_wait(client_socket, addr, filesize, file_path)
        elif protocol == "selective-repeat":
            recieve_selective_repeat(client_socket, addr, filesize, file_path)

        client_socket.sendto(b"UPLOAD_COMPLETE", addr)
        print(f"File {filename} received successfully from {addr}")

    except socket.timeout:
        print(f"Timeout while receiving file from {addr}")
    finally:
        client_socket.close()


def handle_client(server_socket, addr, data, args):
    if data.decode() == "UPLOAD_CLIENT":
        handle_upload(addr, args)

    elif data.decode() == "DOWNLOAD_CLIENT":
        print(f"Client {addr} connected for download.")
        server_socket.sendto(b"DOWNLOAD_ACK", addr)
        # download logic here
        return


def main():
    args = argument_parser()

    if not args.host or not args.port:
        print("Usage: python3 start-server.py <host> <port>")
        sys.exit(1)

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((args.host, args.port))
    print(f"Server listening on {args.host}:{args.port}")

    client_threads = {}

    try:
        while True:
            data, addr = server_socket.recvfrom(1024)
            if addr not in client_threads:
                client_thread = threading.Thread(
                    target=handle_client, args=(server_socket, addr, data, args)
                )
                client_thread.start()
                client_threads[addr] = client_thread
    except KeyboardInterrupt:
        print("Server shutting down.")
    finally:
        for thread in client_threads.values():
            thread.join()
        server_socket.close()


if __name__ == "__main__":
    main()
