import os
import socket
import time

BUFFER = 1024
TIMEOUT = 10
BUFFER_SR = 4096


class SelectiveRepeatProtocol:
    def __init__(self, args, sock: socket.socket):
        self.args = args
        self.socket = sock
        self.socket.settimeout(TIMEOUT)

    def send_upload(self, file_size):
        try:
            with open(self.args.src, "rb") as file:
                window_size = 4 #cant_pkt_env / 2 -> #cant_pkt_env = file_size / channel_size
                base_num = 0
                next_seq_num = 0
                bytes_sent = 0 
                pkts = {}  # Diccionario: {seq_num: (packet, sent_time)}
                timeout = 1.0
                
                while bytes_sent < file_size:
                    while next_seq_num < base_num + window_size and bytes_sent < file_size:
                        chunk = file.read(BUFFER)
                        if not chunk:
                            break
                            
                        bytes_read = len(chunk)
                        packet = f"{next_seq_num}:".encode() + chunk
                        
                        # Guardar paquete y timestamp
                        pkts[next_seq_num] = (packet, time.time())
                        
                        # Enviar paquete
                        self.socket.sendto(packet, (self.args.host, self.args.port))
                        next_seq_num += 1
                        bytes_sent += bytes_read
                    
                    current_time = time.time()
                    for seq_num, (packet, sent_time) in list(pkts.items()):
                        if current_time - sent_time > timeout:
                            print(f"Timeout, reenviando paquete {seq_num}")
                            self.socket.sendto(packet, (self.args.host, self.args.port))
                            pkts[seq_num] = (packet, current_time)  # Actualizar timestamp

                    self.socket.settimeout(0.1)

                    try:
                        data, addr = self.socket.recvfrom(1024)
                        response = data.decode()
                        
                        if response.startswith("ACK:"):
                            ack_seq = int(response.split(":")[1])

                            if ack_seq in pkts:
                                del pkts[ack_seq]
                                
                                if ack_seq == base_num:
                                    while base_num not in pkts and base_num < next_seq_num:
                                        base_num += 1
                                        
                    except socket.timeout:
                        pass
                    
                    # Si todos los paquetes fueron confirmados y hemos enviado todo el archivo
                    if not pkts and bytes_sent >= file_size:
                        break

                self.socket.settimeout(0.5)
                try:
                    while True:
                        data, addr = self.socket.recvfrom(1024)
                except socket.timeout:
                    pass

                self.socket.settimeout(5)
                self.socket.sendto(b"EOF", (self.args.host, self.args.port))
                try:
                    data, addr = self.socket.recvfrom(1024)
                    if data.decode() == "UPLOAD_COMPLETE":
                        print(f"File {self.args.name} uploaded successfully.")
                        return True
                    else:
                        print(f"Unexpected response after EOF: {data.decode()}")
                        return False
                except socket.timeout:
                    print("No response from server after sending EOF.")
                    return False
                
        except Exception as e:
            print(f"Error during transfer: {str(e)}")
            return False

    def receive_upload(
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
                print(f"DEBUG: EOF recibido, enviando UPLOAD_COMPLETE")
                break


    def send_download(self, client_socket, addr, file_path):
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
    

    def recieve_download(args, download_socket, filesize):
        """ 
        Implementación del protocolo Selective Repeat para la recepción de archivos
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