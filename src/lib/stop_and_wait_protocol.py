import socket
import os
import time

CLIENT_TIMEOUT_START = 0.02 
CLIENT_TIMEOUT_MAX = 0.5   
BUFFER = 800 #buffer para mandar paquetes               
PACKET_BUFFER = BUFFER + 50 #buffer para recibir paquetes de datos
SERVER_TIMEOUT = 60.0     
MAX_RETRIES = 20 
BUFFER_ACK = 64 #buffer para recibir ACKs

class StopAndWaitProtocol:
    def __init__(self, args, client_socket: socket.socket):
        self.args = args
        self.socket = client_socket

    def send_upload(self, file_size):
        print(f"CLIENTE: Iniciando envío de {file_size:,} bytes ({file_size/1024/1024:.1f} MB)...")
        
        start_time = time.time()
        
        with open(self.args.src, "rb") as file:
            seq_num = 0
            bytes_sent = 0
            estimated_rtt = None
            current_timeout = CLIENT_TIMEOUT_START
            successful_packets = 0
            packet_count = 0

            while bytes_sent < file_size:
                packet_count += 1

                bytes_to_read = min(BUFFER, file_size - bytes_sent)
                file_position = file.tell()
                chunk = file.read(bytes_to_read)
                bytes_read = len(chunk)
                
                if bytes_read == 0: break

                if packet_count == 1 or packet_count % 100 == 0:
                    progress = (bytes_sent / file_size) * 100
                    elapsed = time.time() - start_time
                    if elapsed > 0:
                        print(f"[PROGRESO: [{packet_count:4d}] - {progress:4.1f}% ]")

                packet = f"{seq_num}:".encode() + chunk
                ack_received = False
                retries = 0
                
                while not ack_received and retries < MAX_RETRIES: 
                    # if retries > 0:
                    #     print(f"    [REINTENTO {retries}/{MAX_RETRIES}] Paquete {seq_num}")
                    
                    self.socket.sendto(packet, (self.args.host, self.args.port))
                    send_time = time.monotonic()
                    
                    try:
                        self.socket.settimeout(current_timeout)
                        data, addr = self.socket.recvfrom(BUFFER_ACK)
                        recv_time = time.monotonic()
                        
                        # RTT measurement
                        sample_rtt = recv_time - send_time
                        if estimated_rtt is None:
                            estimated_rtt = sample_rtt
                        else:
                            estimated_rtt = (0.7 * estimated_rtt) + (0.3 * sample_rtt)
                        
                        # Ajustar timeout
                        current_timeout = max(estimated_rtt * 2.5, CLIENT_TIMEOUT_START)
                        current_timeout = min(current_timeout, CLIENT_TIMEOUT_MAX)

                        response = data.decode().strip()
                        if response == f"ACK:{seq_num}":
                            ack_received = True
                            successful_packets += 1
                            break
                            
                    except socket.timeout:
                        retries += 1
                        current_timeout = min(current_timeout * 1.3, CLIENT_TIMEOUT_MAX)
                        
                        # Releer chunk desde el archivo
                        file.seek(file_position)
                        chunk = file.read(bytes_to_read)
                        packet = f"{seq_num}:".encode() + chunk

                if not ack_received:
                    print(f"ERROR: Paquete {seq_num} falló después de {MAX_RETRIES} intentos")
                    return False
                    
                bytes_sent += bytes_read
                seq_num = 1 - seq_num
            
            print(f"\n--- UPLOAD COMPLETADO ---")
            elapsed_total = time.time() - start_time
            print(f"Archivo enviado: {bytes_sent:,} bytes en {elapsed_total:.1f}s")
            return True

    def receive_upload(self, addr, filename, filesize):
        storage_path = self.args.storage if self.args.storage else "storage"
        os.makedirs(storage_path, exist_ok=True)
        file_path = os.path.join(storage_path, filename)
        
        print(f"SERVIDOR: Recibiendo '{filename}' ({filesize:,} bytes)...")
        total_chunks = (filesize + BUFFER - 1) // BUFFER
        start_time = time.time()
        
        self.socket.settimeout(SERVER_TIMEOUT)
        with open(file_path, "wb") as received_file:
            seq_expected = 0
            bytes_received = 0
            last_correct_seq = -1
            packet_count = 0

            while bytes_received < filesize:
                try:
                    packet, _ = self.socket.recvfrom(PACKET_BUFFER)
                    packet_count += 1
                    
                    if b":" not in packet:
                        print(f"<-- [ERROR] Paquete sin formato ':' - ignorando")
                        continue
                        
                    seq_str, chunk = packet.split(b":", 1)
                    seq_received = int(seq_str)

                    if packet_count == 1 or packet_count % 200 == 0 or bytes_received + len(chunk) >= filesize:
                        progress = ((bytes_received + len(chunk)) / filesize) * 100
                        elapsed = time.time() - start_time
                        if elapsed > 0:
                            print(f"<-- [{packet_count:4d}] {progress:5.1f}% - Paquete {seq_received}")

                    if seq_received == seq_expected:
                        received_file.write(chunk)
                        bytes_received += len(chunk)
                        last_correct_seq = seq_received
                        self.socket.sendto(f"ACK:{seq_received}".encode(), addr)
                        seq_expected = 1 - seq_expected
                        
                        if bytes_received >= filesize:
                            break
                            
                    else:
                        # Paquete duplicado - reenviar ACK
                        if last_correct_seq != -1:
                            self.socket.sendto(f"ACK:{last_correct_seq}".encode(), addr)
                            
                except socket.timeout:
                    print(f"<-- [TIMEOUT] {SERVER_TIMEOUT}s - Cliente desconectado")
                    return False, filename
                except (ValueError, UnicodeDecodeError) as e:
                    print(f"<-- [ERROR] {type(e).__name__} - ignorando paquete")
                    continue

        elapsed_total = time.time() - start_time
        rate = (bytes_received / 1024 / 1024) / max(elapsed_total, 0.001)
        
        print(f"\n--- RECEPCIÓN COMPLETADA ---")
        print(f"Archivo: {filename} ({bytes_received:,} bytes)")
        print(f"Tiempo: {elapsed_total:.1f}s")

        # Esperar posibles paquetes duplicados antes de cerrar
        end_time = time.time() + 2
        while time.time() < end_time:
            try:
                self.socket.settimeout(0.5)
                packet, _ = self.socket.recvfrom(PACKET_BUFFER)
                if b":" in packet:
                    seq_str, chunk = packet.split(b":", 1)
                    seq_received = int(seq_str)
                    if seq_received == (1 - seq_expected):
                        self.socket.sendto(f"ACK:{seq_received}".encode(), addr)
            except:
                continue

        return True, filename
    
    def send_download(self, addr, filename, filesize):
        storage_path = self.args.storage if self.args.storage else "storage"
        file_path = os.path.join(storage_path, filename)
        
        print(f"SERVIDOR: Enviando archivo '{filename}' ({filesize:,} bytes) a {addr}")
        
        start_time = time.time()
        
        with open(file_path, "rb") as file:
            seq_num = 0
            bytes_sent = 0
            estimated_rtt = None
            current_timeout = CLIENT_TIMEOUT_START
            packet_count = 0

            while bytes_sent < filesize:
                packet_count += 1

                bytes_to_read = min(BUFFER, filesize - bytes_sent)
                file_position = file.tell()
                chunk = file.read(bytes_to_read)
                bytes_read = len(chunk)
                
                if bytes_read == 0: break

                if packet_count == 1 or packet_count % 100 == 0:
                    progress = (bytes_sent / filesize) * 100
                    elapsed = time.time() - start_time
                    if elapsed > 0:
                        print(f"[PROGRESO: [{packet_count:4d}] - {progress:4.1f}% ]")

                packet = f"{seq_num}:".encode() + chunk
                ack_received = False
                retries = 0
                
                while not ack_received and retries < MAX_RETRIES: 
                    if retries > 0:
                        print(f"    [REINTENTO {retries}/{MAX_RETRIES}] Paquete {seq_num}")
                    
                    self.socket.sendto(packet, addr)
                    send_time = time.monotonic()
                    
                    try:
                        self.socket.settimeout(current_timeout)
                        data, _ = self.socket.recvfrom(BUFFER_ACK)
                        recv_time = time.monotonic()
                        
                        # RTT measurement
                        sample_rtt = recv_time - send_time
                        if estimated_rtt is None:
                            estimated_rtt = sample_rtt
                        else:
                            estimated_rtt = (0.7 * estimated_rtt) + (0.3 * sample_rtt)
                        
                        # Ajustar timeout
                        current_timeout = max(estimated_rtt * 2.5, CLIENT_TIMEOUT_START)
                        current_timeout = min(current_timeout, CLIENT_TIMEOUT_MAX)

                        response = data.decode().strip()
                        if response == f"ACK:{seq_num}":
                            ack_received = True
                            break
                            
                    except socket.timeout:
                        retries += 1
                        current_timeout = min(current_timeout * 1.3, CLIENT_TIMEOUT_MAX)
                        
                        # Releer chunk
                        file.seek(file_position)
                        chunk = file.read(bytes_to_read)
                        packet = f"{seq_num}:".encode() + chunk

                if not ack_received:
                    print(f"ERROR: Paquete {seq_num} falló después de {MAX_RETRIES} intentos")
                    return False
                    
                bytes_sent += bytes_read
                seq_num = 1 - seq_num

            elapsed_total = time.time() - start_time
            print(f"SERVIDOR: Archivo enviado: {bytes_sent:,} bytes en {elapsed_total:.1f}s")
            return True

    def receive_download(self, filesize):
        if os.path.isdir(self.args.dst):
            file_path = os.path.join(self.args.dst, self.args.name)
        else:
            file_path = self.args.dst
            
        print(f"CLIENTE: Recibiendo '{self.args.name}' ({filesize:,} bytes)...")
        print(f"CLIENTE: Guardando en: {file_path}")
        
        start_time = time.time()
        self.socket.settimeout(SERVER_TIMEOUT)
        
        with open(file_path, "wb") as received_file:
            seq_expected = 0
            bytes_received = 0
            last_correct_seq = -1
            packet_count = 0

            while bytes_received < filesize:
                try:
                    packet, _ = self.socket.recvfrom(PACKET_BUFFER)
                    packet_count += 1
                    
                    if b":" not in packet:
                        print(f"<-- [ERROR] Paquete sin formato ':' - ignorando")
                        continue
                        
                    seq_str, chunk = packet.split(b":", 1)
                    seq_received = int(seq_str)

                    # Progreso cada 200 paquetes
                    if packet_count == 1 or packet_count % 200 == 0 or bytes_received + len(chunk) >= filesize:
                        progress = ((bytes_received + len(chunk)) / filesize) * 100
                        elapsed = time.time() - start_time
                        if elapsed > 0:
                            print(f"<-- [{packet_count:4d}] {progress:5.1f}% - Paquete {seq_received}")

                    if seq_received == seq_expected:
                        received_file.write(chunk)
                        bytes_received += len(chunk)
                        last_correct_seq = seq_received
                        self.socket.sendto(f"ACK:{seq_received}".encode(), (self.args.host, self.args.port))
                        seq_expected = 1 - seq_expected
                        
                        if bytes_received >= filesize:
                            break
                            
                    else:
                        # Paquete duplicado - reenviar último ACK correcto
                        if last_correct_seq != -1:
                            self.socket.sendto(f"ACK:{last_correct_seq}".encode(), (self.args.host, self.args.port))
                            
                except socket.timeout:
                    print(f"<-- [TIMEOUT] {SERVER_TIMEOUT}s - Servidor desconectado")
                    return False
                except (ValueError, UnicodeDecodeError) as e:
                    print(f"<-- [ERROR] {type(e).__name__} - ignorando paquete")
                    continue

        elapsed_total = time.time() - start_time
        
        print(f"\n--- DESCARGA COMPLETADA ---")
        print(f"Archivo: {self.args.name} ({bytes_received:,} bytes)")
        print(f"Tiempo: {elapsed_total:.1f}s")
        print(f"Guardado en: {file_path}")

        return True