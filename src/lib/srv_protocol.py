import os
import socket
from lib.stop_and_wait_protocol import StopAndWaitProtocol
from lib.selective_repeat_protocol import SelectiveRepeatProtocol

TIMEOUT = 10
BUFFER = 1024
BUFFER_SR = 4096
BUFFER_SW = 4096


class ServerProtocol:
    def __init__(self, args):
        self.args = args

    def handle_upload(self, addr):
        print(f"Client {addr} connected for upload.")

        client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        client_socket.bind(("", 0))
        client_port = client_socket.getsockname()[1]

        client_socket.sendto(b"UPLOAD_ACK", addr)
        client_socket.sendto(f"PORT:{client_port}".encode(), addr)
        client_socket.settimeout(TIMEOUT)

        try:
            protocol_data, _ = client_socket.recvfrom(BUFFER)
            protocol = protocol_data.decode()
            print(f"Client using protocol: {protocol}")
            client_socket.sendto(b"PROTOCOL_ACK", addr)

            file_info, addr = client_socket.recvfrom(BUFFER)
            filename, filesize = file_info.decode().split(":")
            filesize = int(filesize)
            print(f"Receiving file {filename} of size {filesize} bytes from {addr}")
            client_socket.sendto(b"FILE_INFO_ACK", addr)

            # C = A si A, caso contrario B
            storage_path = self.args.storage if self.args.storage else "storage"
            os.makedirs(storage_path, exist_ok=True)
            file_path = os.path.join(storage_path, filename)

            if protocol == "stop-and-wait":
                stop_and_wait = StopAndWaitProtocol(self.args, client_socket)
                stop_and_wait.receive_upload(client_socket, addr, filesize, file_path)
            elif protocol == "selective-repeat":
                selective_repeat = SelectiveRepeatProtocol(self.args, client_socket)
                selective_repeat.receive_upload(client_socket, addr, filesize, file_path)

            client_socket.sendto(b"UPLOAD_COMPLETE", addr)
            print(f"File {filename} received successfully from {addr}")

            # Se podria cortar la conexion una vez terminado todo y no esperar por el timeout

        except socket.timeout:
            print(f"Timeout while receiving file from {addr}")
        finally:
            client_socket.close()

    def handle_download(self, addr):
        print(f"Client {addr} connected for download.")

        # socket temporal del cliente
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        client_socket.bind(("", 0))
        client_port = client_socket.getsockname()[1]
        client_socket.settimeout(TIMEOUT)

        try:
            # envio ack y nro de puerto
            client_socket.sendto(b"DOWNLOAD_ACK", addr)
            client_socket.sendto(f"PORT:{client_port}".encode(), addr)

            # recibo protocolo, y envío ack
            protocol_data, _ = client_socket.recvfrom(BUFFER)
            protocol = protocol_data.decode()
            client_socket.sendto(b"PROTOCOL_ACK", addr)

            # recibo nombre del archivo
            filename_data, _ = client_socket.recvfrom(BUFFER)
            filename = filename_data.decode()
            
            # constituyo la ruta del archivo
            storage_path = self.args.storage if self.args.storage else "storage"
            file_path = os.path.join(storage_path, filename)

            # chequeo existencia, envío info al y espero ack para enviar archivo
            if os.path.isfile(file_path):
                filesize = os.path.getsize(file_path)
                client_socket.sendto(f"FILESIZE:{filesize}".encode(), addr)
                ack_info, _ = client_socket.recvfrom(BUFFER)
                if ack_info.decode() != "FILE_INFO_ACK":
                    return
            else:
                client_socket.sendto(b"ERROR:FileNotFound", addr)
                return

            if protocol == "stop-and-wait":
                stop_and_wait = StopAndWaitProtocol(self.args, client_socket)
                success = stop_and_wait.send_download(client_socket, addr, file_path)
            # elif protocol == "selective-repeat":
            #     success = self.send_selective_repeat(client_socket, addr, file_path)

            if success:
                print(f"File '{filename}' sent successfully to {addr}.")
            else:
                print(f"Failed to send file '{filename}' to {addr}.")

        except socket.timeout: # si hay timeout
            print(f"Timeout during negotiation with client {addr}.")
        finally: # en ambos casos, cierro el socket temporal
            client_socket.close()

    def handle_client(self, addr, data) -> None:
        message = data.decode()
        if message == "UPLOAD_CLIENT":
            self.handle_upload(addr)
        elif message == "DOWNLOAD_CLIENT":
            self.handle_download(addr)
        else:
            print(f"Unknown client message from {addr}: {message}")
