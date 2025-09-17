import os
import socket

TIMEOUT = 10
BUFFER = 1024
BUFFER_SR = 4096
BUFFER_SW = 4096


class ServerProtocol:
    def __init__(self, args):
        self.args = args

    def recieve_selective_repeat(
    self, client_socket: socket.socket, addr, filesize: int, file_path: str
):
        seq_expected = 0
        bytes_received = 0
        buffer = []

        with open(file_path, "wb") as recieved_file:
            while bytes_received < filesize:
                packet, saddr = client_socket.recvfrom(BUFFER_SR)
                    
                try:
                    seq_str, chunk = packet.split(b":", 1)
                    seq_received = int(seq_str)
                except Exception:
                    print(f"Packet format error from {addr}, ignoring.")
                    continue
                    
                if seq_received == seq_expected:
                    recieved_file.write(chunk)
                    bytes_received += len(chunk)
                    seq_expected += 1

                    if buffer:
                        buffer.sort(key=lambda x: x[0])
                        
                        i = 0
                        while i < len(buffer):
                            if buffer[i][0] == seq_expected:
                                buffer_chunk = buffer[i][1]
                                recieved_file.write(buffer_chunk)
                                bytes_received += len(buffer_chunk)
                                seq_expected += 1
                                buffer.pop(i)
                            else:
                                i += 1
                    
                    client_socket.sendto(f"ACK:{seq_received}".encode(), addr)
                else:
                    print(f"Received packet {seq_received}, expected {seq_expected} - queuing")
                    buffer.append((seq_received, chunk))
                    client_socket.sendto(f"ACK:{seq_received}".encode(), addr)
        
        while True:
            packet, addr = client_socket.recvfrom(BUFFER)
            if packet == b"EOF":
                break

    def recieve_stop_and_wait(
        self, client_socket: socket.socket, addr, filesize: int, file_path: str
    ):
        """
            Recibe un archivo usando el protocolo Stop-and-Wait.
            Args:
            client_socket (socket.socket): El socket UDP para la comunicación.
            addr: La dirección del cliente.
            filesize (int): El tamaño del archivo a recibir.
            file_path (str): La ruta donde se guardará el archivo recibido.
            Explicacion paso a paso:
            1. Abre el archivo en modo escritura binaria.
            2. Inicializa el número de secuencia esperado y los bytes recibidos.
            3. Inicia un bucle que continúa hasta que se hayan recibido todos los bytes

            del archivo.
            4. Dentro del bucle, recibe un paquete del cliente.
            5. Extrae el número de secuencia y el contenido del paquete.
            6. Si el número de secuencia es el esperado:
            - Escribe el contenido en el archivo.
            - Incrementa el número de secuencia esperado y los bytes recibidos.
            - Envía un ACK al cliente.
            7. Si el número de secuencia no es el esperado:
            - Ignora el paquete y reenvía el ACK del último paquete correcto.
            8. Finalmente, espera el paquete EOF para confirmar la finalización de la transferencia.

        """
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

    def send_selective_repeat(self, client_socket, addr, file_path):
        try:

            client_socket.settimeout(TIMEOUT)

            filesize = os.path.getsize(file_path)
            success = True

            with open(file_path, "rb") as file:
                base = 0
                next_seq_num = 0
                window_size = 4
                buffer = {}
                bytes_sent = 0

                while bytes_sent < filesize or buffer:
                    while next_seq_num < base + window_size and bytes_sent < filesize:
                        chunk = file.read(1024)
                        if not chunk:
                            break
                        
                        packet = f"{next_seq_num}:".encode() + chunk
                        client_socket.sendto(packet, addr)
                        buffer[next_seq_num] = chunk
                        next_seq_num += 1
                        bytes_sent += len(chunk)

                    try:
                        data, _ = client_socket.recvfrom(1024)
                        response = data.decode()
                        if response.startswith("ACK:"):
                            ack_num = int(response.split(":")[1])
                            if ack_num in buffer:
                                del buffer[ack_num]
                                if ack_num == base:
                                    while base not in buffer and base < next_seq_num:
                                        base += 1
                    except socket.timeout:
                        print("Timeout waiting for ACKs, resending unacknowledged packets...")
                        for seq in range(base, next_seq_num):
                            if seq in buffer:
                                packet = f"{seq}:".encode() + buffer[seq]
                                client_socket.sendto(packet, addr)

                client_socket.sendto(b"EOF", addr)

            return success

        except FileNotFoundError:
            print(f"Error: File not found at {file_path}")
            success = False
            return success
                
    def send_stop_and_wait(self, client_socket, addr, file_path):
        try:

            client_socket.settimeout(TIMEOUT)

            filesize = os.path.getsize(file_path)
            success = True

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
                        success = False
                        return success

        except FileNotFoundError:
            print(f"Error: File not found at {file_path}")
            success = False
            return success

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
                success = self.send_stop_and_wait(client_socket, addr, file_path)
            elif protocol == "selective-repeat":
                success = self.send_selective_repeat(client_socket, addr, file_path)

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
