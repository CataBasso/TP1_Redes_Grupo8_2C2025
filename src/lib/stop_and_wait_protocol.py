import socket
import os
import time
import logging
CLIENT_TIMEOUT_START = 0.02 
CLIENT_TIMEOUT_MAX = 0.5   
BUFFER = 800 #buffer para mandar paquetes               
PACKET_BUFFER = BUFFER + 50 #buffer para recibir paquetes de datos
SERVER_TIMEOUT = 120.0    
MAX_RETRIES = 20 
BUFFER_ACK = 64 #buffer para recibir ACKs

class StopAndWaitProtocol:
    def __init__(self, args, client_socket: socket.socket):
        self.args = args
        self.socket = client_socket

    def show_progress_bar(self, current, total, bar_length=50):
        """Muestra una barra de progreso ASCII"""
        progress = current / total
        filled_length = int(bar_length * progress)
        
        bar = '█' * filled_length + '-' * (bar_length - filled_length)
        percent = progress * 100


        logging.info(f'\r[{bar}] {percent:.1f}% ({current}/{total})')

        if progress >= 1.0:
            logging.info("")

    def send_upload(self, file_size):
        logging.info(f"CLIENTE: Iniciando envío de {file_size:,} bytes ({file_size/1024/1024:.1f} MB)...")
        
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
                    elapsed = time.time() - start_time
                    if elapsed > 0:
                        self.show_progress_bar(bytes_sent, file_size)

                packet = f"{seq_num}:".encode() + chunk
                ack_received = False
                retries = 0
                
                while not ack_received and retries < MAX_RETRIES: 
                    logging.debug(f"Enviando paquete seq={seq_num}, intento={retries+1}, bytes={len(packet)}")
                    self.socket.sendto(packet, (self.args.host, self.args.port))
                    send_time = time.monotonic()
                    try:
                        self.socket.settimeout(current_timeout)
                        data, addr = self.socket.recvfrom(BUFFER_ACK)
                        recv_time = time.monotonic()
                        logging.debug(f"Recibido ACK de {addr}: {data}")
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
                        logging.debug(f"Respuesta recibida: {response}")
                        if response == f"ACK:{seq_num}":
                            ack_received = True
                            successful_packets += 1
                            logging.debug(f"ACK correcto para seq={seq_num}")
                            break
                        else:
                            logging.debug(f"ACK incorrecto para seq={seq_num}: {response}")
                    except socket.timeout:
                        retries += 1
                        current_timeout = min(current_timeout * 1.3, CLIENT_TIMEOUT_MAX)
                        logging.debug(f"Timeout esperando ACK para seq={seq_num}, reintentando (intento {retries})")
                        # Releer chunk desde el archivo
                        file.seek(file_position)
                        chunk = file.read(bytes_to_read)
                        packet = f"{seq_num}:".encode() + chunk

                if not ack_received:
                    logging.error(f"Paquete {seq_num} falló después de {MAX_RETRIES} intentos")
                    return False
                    
                bytes_sent += bytes_read
                seq_num = 1 - seq_num
            
            self.show_progress_bar(bytes_sent, file_size)
            logging.info(f"\n--- UPLOAD COMPLETADO ---")
            elapsed_total = time.time() - start_time
            logging.info(f"Archivo enviado: {bytes_sent:,} bytes en {elapsed_total:.1f}s")
            return True

    def receive_upload(self, addr, filename, filesize):
        storage_path = self.args.storage if self.args.storage else "storage"
        os.makedirs(storage_path, exist_ok=True)
        file_path = os.path.join(storage_path, filename)

        logging.info(f"SERVIDOR: Recibiendo '{filename}' ({filesize:,} bytes)...")
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
                        logging.error(f"<-- [ERROR] Paquete sin formato ':' - ignorando")
                        continue
                    seq_str, chunk = packet.split(b":", 1)
                    seq_received = int(seq_str)
                    logging.debug(f"Recibido paquete seq={seq_received}, bytes={len(chunk)}")
                    if packet_count == 1 or packet_count % 200 == 0 or bytes_received + len(chunk) >= filesize:
                        progress = ((bytes_received + len(chunk)) / filesize) * 100
                        elapsed = time.time() - start_time
                        if elapsed > 0:
                            self.show_progress_bar(bytes_received + len(chunk), filesize)
                    if seq_received == seq_expected:
                        received_file.write(chunk)
                        bytes_received += len(chunk)
                        last_correct_seq = seq_received
                        logging.debug(f"ACK enviado para seq={seq_received}")
                        self.socket.sendto(f"ACK:{seq_received}".encode(), addr)
                        seq_expected = 1 - seq_expected
                        if bytes_received >= filesize:
                            break
                    else:
                        # Paquete duplicado - reenviar ACK
                        logging.debug(f"Paquete duplicado seq={seq_received}, reenviando ACK para seq={last_correct_seq}")
                        if last_correct_seq != -1:
                            self.socket.sendto(f"ACK:{last_correct_seq}".encode(), addr)
                            
                except socket.timeout:
                    logging.warning(f"<-- [TIMEOUT] {SERVER_TIMEOUT}s - Cliente desconectado")
                    return False, filename
                except (ValueError, UnicodeDecodeError) as e:
                    logging.error(f"<-- [ERROR] {type(e).__name__} - ignorando paquete")
                    continue

        elapsed_total = time.time() - start_time

        logging.info(f"\n--- RECEPCIÓN COMPLETADA ---")
        logging.info(f"Archivo: {filename} ({bytes_received:,} bytes)")
        logging.info(f"Tiempo: {elapsed_total:.1f}s")

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

        logging.info(f"SERVIDOR: Enviando archivo '{filename}' ({filesize:,} bytes) a {addr}")

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
                    elapsed = time.time() - start_time
                    if elapsed > 0:
                        self.show_progress_bar(bytes_sent, filesize)

                packet = f"{seq_num}:".encode() + chunk
                ack_received = False
                retries = 0
                
                while not ack_received and retries < MAX_RETRIES:   
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
                    logging.error(f"Paquete {seq_num} falló después de {MAX_RETRIES} intentos")
                    return False
                    
                bytes_sent += bytes_read
                seq_num = 1 - seq_num

            self.show_progress_bar(bytes_sent, filesize)
            elapsed_total = time.time() - start_time
            logging.info(f"\n--- DOWNLOAD COMPLETADO ---")
            logging.info(f"Archivo enviado: {bytes_sent:,} bytes")
            logging.info(f"Tiempo: {elapsed_total:.1f}s")
            return True

    def receive_download(self, filesize):
        if os.path.isdir(self.args.dst):
            file_path = os.path.join(self.args.dst, self.args.name)
        else:
            file_path = self.args.dst

        logging.info(f"CLIENTE: Recibiendo '{self.args.name}' ({filesize:,} bytes)...")
        logging.info(f"CLIENTE: Guardando en: {file_path}")

        start_time = time.time()
        self.socket.settimeout(SERVER_TIMEOUT)
        
        with open(file_path, "wb") as received_file:
            seq_expected = 0
            bytes_received = 0
            last_correct_seq = -1
            packet_count = 0

            while bytes_received < filesize:
                try:
                    packet, server_addr = self.socket.recvfrom(PACKET_BUFFER)
                    packet_count += 1
                    
                    if b":" not in packet:
                        logging.error(f"<-- [ERROR] Paquete sin formato ':' - ignorando")
                        continue
                        
                    seq_str, chunk = packet.split(b":", 1)
                    seq_received = int(seq_str)

                    # Progreso cada 200 paquetes
                    if packet_count == 1 or packet_count % 200 == 0 or bytes_received + len(chunk) >= filesize:
                        elapsed = time.time() - start_time
                        if elapsed > 0:
                            self.show_progress_bar(bytes_received + len(chunk), filesize)

                    if seq_received == seq_expected:
                        received_file.write(chunk)
                        bytes_received += len(chunk)
                        last_correct_seq = seq_received
                        self.socket.sendto(f"ACK:{seq_received}".encode(), server_addr)
                        seq_expected = 1 - seq_expected
                        
                        if bytes_received >= filesize:
                            break
                            
                    else:
                        # Paquete duplicado - reenviar último ACK correcto
                        if last_correct_seq != -1:
                            self.socket.sendto(f"ACK:{last_correct_seq}".encode(), server_addr)
                            
                except socket.timeout:
                    logging.warning(f"<-- [TIMEOUT] {SERVER_TIMEOUT}s - Servidor desconectado")
                    return False
                except (ValueError, UnicodeDecodeError) as e:
                    logging.error(f"<-- [ERROR] {type(e).__name__} - ignorando paquete")
                    continue

        elapsed_total = time.time() - start_time

        logging.info(f"\n--- DESCARGA COMPLETADA ---")
        logging.info(f"Archivo: {self.args.name} ({bytes_received:,} bytes)")
        logging.info(f"Tiempo: {elapsed_total:.1f}s")
        logging.info(f"Guardado en: {file_path}")

        end_time = time.time() + 2
        while time.time() < end_time:
            try:
                self.socket.settimeout(0.5)
                packet, _ = self.socket.recvfrom(PACKET_BUFFER)
                if b":" in packet:
                    seq_str, chunk = packet.split(b":", 1)
                    seq_received = int(seq_str)
                    if seq_received == (1 - seq_expected):
                        self.socket.sendto(f"ACK:{seq_received}".encode(), server_addr)
            except:
                continue

        return True