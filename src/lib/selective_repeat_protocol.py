import socket
import time

BUFFER = 1024
TIMEOUT = 1.0

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