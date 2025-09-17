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