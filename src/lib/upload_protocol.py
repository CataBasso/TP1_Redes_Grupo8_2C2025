import socket
import os
import time
from lib.stop_and_wait_protocol import StopAndWaitProtocol

TIMEOUT = 5
BUFFER = 1024

class UploadProtocol:
    def __init__(self, args):
        self.args = args
        self.socket = None

    def establish_connection(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.settimeout(TIMEOUT)
        print(f"Connecting to server at {self.args.host}:{self.args.port}")
        self.socket.sendto(b"UPLOAD_CLIENT", (self.args.host, self.args.port))
        try:
            data, addr = self.socket.recvfrom(BUFFER)
            if data.decode() != "UPLOAD_ACK":
                print("Server did not acknowledge upload client.")
                return False
            
            new_port_data, addr = self.socket.recvfrom(BUFFER)
            if new_port_data.decode().startswith("PORT:"):
                new_port = int(new_port_data.decode().split(":")[1])
                print(f"Server assigned port {new_port} for file upload.")
                self.args.port = new_port
            else:
                print("Did not receive new port from server.")
                return False
        except socket.timeout:
            print("No response from server, exiting.")
            return False

        return True
    
    def send_protocol_info(self):
        protocol = self.args.protocol if self.args.protocol else "stop-and-wait"
        self.socket.sendto(protocol.encode(), (self.args.host, self.args.port))

        try:
            data, addr = self.socket.recvfrom(BUFFER)
            if data.decode() != "PROTOCOL_ACK":
                print("Server did not acknowledge protocol choice.")
                return False
        except socket.timeout:
            print("No response from server after sending protocol choice, exiting.")
            return False
            
        return True

    def send_file_info(self):
        if not os.path.isfile(self.args.src):
            print(f"Source file {self.args.src} does not exist.")
            return None

        file_size = os.path.getsize(self.args.src)
        print(f"Uploading file {self.args.name} of size {file_size} bytes.")

        file_info = f"{self.args.name}:{file_size}"
        self.socket.sendto(file_info.encode(), (self.args.host, self.args.port))

        try:
            data, addr = self.socket.recvfrom(BUFFER)
            if data.decode() != "FILE_INFO_ACK":
                print("Server did not acknowledge file info.")
                return None
        except socket.timeout:
            print("No response from server after sending file info, exiting.")
            return None
        
        return file_size

    def send_selective_repeat(self, file_size):
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

    def upload_file(self):
        if not self.establish_connection():
            return False

        if not self.send_protocol_info():
            return False

        file_size = self.send_file_info()
        if file_size is None:
            return False

        protocol = self.args.protocol if self.args.protocol else "stop-and-wait"
        if protocol == "stop-and-wait":
            stop_and_wait = StopAndWaitProtocol(self.args, self.socket)
            return stop_and_wait.send_upload(file_size)
        elif protocol == "selective-repeat":
            return self.send_selective_repeat(file_size)
