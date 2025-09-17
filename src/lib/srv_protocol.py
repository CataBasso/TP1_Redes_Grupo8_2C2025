import os
import socket

TIMEOUT = 10
BUFFER = 1024
BUFFER_SR = 4096
BUFFER_SW = 4096


class ServerProtocol:
    def __init__(self, server_socket: socket.socket, args):
        #self.server_socket = server_socket
        self.args = args

    def recieve_selective_repeat(
        self, client_socket: socket.socket, addr, filesize: int, file_path: str
    ):
        # lo que tengo que hacer basicamente es
        # recibir paquetes, ver si estan en orden,
        # si el paquete recibido está en orden, envio un ack
        # si el paquete recibido no está en orden, lo buffereo
        # cuando buffereo envio el ack del que recibi
        # en algun momento voy a volver a recibir el paquete perdido, una vez q lo recibi, saco todo del buffer
        # y envio el ack del paquete recibido
        seq_expected = 0
        bytes_received = 0
        buffer = []
        while bytes_received < filesize:
            packet, saddr = client_socket.recvfrom(BUFFER_SR)
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
                if len(buffer) > 0:
                    seq_expected += 1
                    # deliver pkts in buffer, basicamente me permite ir hasta el proximo paquete perdido
                    # te envio hasta el proximo paquete que se haya perdido
                    # voy aumentando el expected hasta llegar al elemento del buffer que no este en orden ahi dejo de hacer pop
                    for i in buffer:
                        if seq_expected == i[0]:
                            print(f"delivered: {seq_expected}")
                            seq_expected += 1  # se supone que en la primera posicion me quedo el ACK del último recibido válido
                        else:
                            print("have in buffer another packet loss")
                client_socket.sendto(f"ACK:{seq_received}".encode(), addr)
            else:
                print("rec != expected: queued")
                buffer.append((seq_received, chunk))
                client_socket.sendto(f"ACK:{seq_received}".encode(), addr)

    def recieve_stop_and_wait(
        self, client_socket: socket.socket, addr, filesize: int, file_path: str
    ):
        with open(file_path, "wb") as recieved_file:
            seq_expected = 0
            bytes_received = 0
            while bytes_received < filesize:
                packet, saddr = client_socket.recvfrom(BUFFER_SW)
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
                eof, saddr = client_socket.recvfrom(BUFFER)
                
    def send_stop_and_wait(self, client_socket, addr, file_path):
        try:
            filesize = os.path.getsize(file_path)
            with open(file_path, "rb") as file:
                seq_num = 0
                bytes_sent = 0
                while bytes_sent < filesize:
                    chunk = file.read(1024)
                    if not chunk:
                        break
                    
                    packet = f"{seq_num}:".encode() + chunk
                    ack_received = False
                    retries = 0
                    max_retries = 5

                    while not ack_received and retries < max_retries:
                        client_socket.sendto(packet, addr)
                        try:
                            data, _ = client_socket.recvfrom(1024)
                            response = data.decode()
                            if response == f"ACK:{seq_num}":
                                ack_received = True
                                bytes_sent += len(chunk)
                                seq_num = 1 - seq_num
                            else:
                                print(f"Received unexpected ACK: {response}, expecting ACK:{seq_num}")
                        except socket.timeout:
                            retries += 1
                            print(f"Timeout waiting for ACK:{seq_num}, retrying {retries}/{max_retries}...")
                    
                    if not ack_received:
                        print("Transfer failed: Max retries reached.")
                        return

        except FileNotFoundError:
            print(f"Error: File not found at {file_path}")
            return
    
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

            # TODO: Preguntarle a Cata que onda con "saddr"
            file_info, saddr = client_socket.recvfrom(BUFFER)
            filename, filesize = file_info.decode().split(":")
            filesize = int(filesize)
            print(f"Receiving file {filename} of size {filesize} bytes from {addr}")
            client_socket.sendto(b"FILE_INFO_ACK", addr)

            # C = A si A, caso contrario B
            storage_path = self.args.storage if self.args.storage else "storage"
            os.makedirs(storage_path, exist_ok=True)
            file_path = os.path.join(storage_path, filename)

            if protocol == "stop-and-wait":
                self.recieve_stop_and_wait(client_socket, addr, filesize, file_path)
            elif protocol == "selective-repeat":
                self.recieve_selective_repeat(client_socket, addr, filesize, file_path)

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
        client_socket.bind(("", 0)) # puerto aleatorio
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
                self.send_stop_and_wait(client_socket, addr, file_path)
            # elif protocol == "selective-repeat":
            #     self.send_selective_repeat(client_socket, addr, file_path)
            
            print(f"File '{filename}' sent successfully to {addr}.")

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
