import socket
import os
import time

BUFFER = 1024
TIMEOUT = 2

class StopAndWaitProtocol:
    def __init__(self, args, client_socket: socket.socket):
        self.args = args
        self.socket = client_socket
        self.socket.settimeout(TIMEOUT)
    
    def send_upload(self, file_size):
        print(f"CLIENTE: Iniciando el envío del archivo de {file_size} bytes...")
        with open(self.args.src, "rb") as file:
            seq_num = 0
            bytes_sent = 0
            packet_count = 0
            
            while bytes_sent < file_size:
                packet_count += 1
                
                # Calcular cuánto leer (puede ser menos que BUFFER al final)
                bytes_to_read = min(BUFFER, file_size - bytes_sent)
                chunk = file.read(bytes_to_read)
                bytes_read = len(chunk)
                
                # Verificación crítica: si no leímos nada, salir
                if bytes_read == 0:
                    print(f"WARNING: EOF alcanzado. bytes_sent={bytes_sent}, file_size={file_size}")
                    break
                
                # Calcular progreso correctamente
                bytes_remaining = file_size - bytes_sent
                progress_percent = (bytes_sent / file_size) * 100
                
                print(f"\n--- CHUNK {packet_count} ---")
                print(f"Progreso: {bytes_sent}/{file_size} bytes ({progress_percent:.1f}%)")
                print(f"Quedan: {bytes_remaining} bytes por enviar")
                print(f"Leyendo {bytes_read} bytes (de {bytes_to_read} solicitados)")

                packet = f"{seq_num}:".encode() + chunk

                ack_received = False
                retries = 0
                max_retries = 10

                current_timeout = 0.5
                max_timeout = 3.0

                while not ack_received and retries < max_retries: 
                    print(f"--> [ENVÍO] Paquete {seq_num} ({bytes_read} bytes)")
                    self.socket.sendto(packet, (self.args.host, self.args.port))
                    
                    try:
                        self.socket.settimeout(current_timeout)
                        print(f"    [ESPERA] Esperando ACK para paquete {seq_num}...")
                        data, addr = self.socket.recvfrom(BUFFER)
                        response = data.decode()  
                        print(f"<-- [RECIBO] Recibido '{response}'")

                        if response == f"ACK:{seq_num}":
                            print(f"    [ÉXITO] ACK para paquete {seq_num} es correcto.")
                            ack_received = True
                            if retries == 0:
                                current_timeout = max(current_timeout * 0.9, 0.3)
                        else:
                            print(f"    [IGNORAR] ACK incorrecto: {response}, esperaba ACK:{seq_num}")
                            pass
                    except socket.timeout:
                        retries += 1
                        current_timeout = min(current_timeout * 1.8, max_timeout)
                        print(f"    [TIMEOUT] Timeout {retries}/{max_retries}")

                if not ack_received:
                    print(f"ERROR: No se pudo enviar el paquete {seq_num} después de {max_retries} intentos")
                    return False
                    
                # Actualizar progreso
                bytes_sent += bytes_read
                seq_num = 1 - seq_num
                
                final_progress = (bytes_sent / file_size) * 100
                print(f"    [ACTUALIZADO] {bytes_sent}/{file_size} bytes enviados ({final_progress:.1f}%)")
                
                # Verificación de terminación
                if bytes_sent >= file_size:
                    print(f"    [COMPLETO] Todos los bytes han sido enviados!")
                    break

        print(f"Archivo '{self.args.name}' subido correctamente - {bytes_sent} bytes transferidos.")
        print(f"Verificación final: {bytes_sent} de {file_size} bytes ({(bytes_sent/file_size)*100:.1f}%)")
        return True
        

    def receive_upload(self, addr, filename, filesize):
    # Ya tenemos el nombre y tamaño, así que construimos la ruta directamente
        storage_path = self.args.storage if self.args.storage else "storage"
        os.makedirs(storage_path, exist_ok=True)
        file_path = os.path.join(storage_path, filename)
        
        print(f"SERVIDOR: Preparado para recibir datos para '{filename}'...")

        with open(file_path, "wb") as received_file:
            seq_expected = 0
            bytes_received = 0
            last_correct_seq = -1
            packet_count = 0

            while bytes_received < filesize:
                try:
                    packet, _ = self.socket.recvfrom(BUFFER)
                    packet_count += 1
                    # seq_str, chunk = packet.split(b":", 1)
                    # seq_received = int(seq_str)
                    if b":" not in packet:
                        print(f"<-- [ERROR] Paquete {packet_count} sin formato ':' - ignorando")
                        continue
                    seq_str, chunk = packet.split(b":", 1)
                    seq_received = int(seq_str)
                    chunk_size = len(chunk)    

                    print(f"<-- [RECIBO-DATOS] Paquete {seq_received} ({chunk_size} bytes)")

                    if seq_received == seq_expected:
                        received_file.write(chunk)
                        bytes_received += len(chunk)
                        last_correct_seq = seq_received

                        print(f"-> Envío ACK {seq_received}")
                        self.socket.sendto(f"ACK:{seq_received}".encode(), addr)
                        seq_expected = 1 - seq_expected
                        
                        if packet_count % 50 == 0:
                            progress = (bytes_received / filesize) * 100
                            print(f"    [PROGRESO-SERVIDOR] {bytes_received}/{filesize} bytes ({progress:.1f}%)")
                    else:
                        print(f"<-- Esperaba seq:{seq_expected}, recibido seq:{seq_received} - paquete duplicado")
                        if last_correct_seq != -1:
                            ack_msg = f"ACK:{last_correct_seq}"
                            print(f"--> [REENVÍO-ACK] {ack_msg}")
                            self.socket.sendto(ack_msg.encode(), addr)
                except (socket.timeout, ValueError) as e:
                    print(f"<-- [ERROR] Error procesando paquete: {type(e).__name__} - ignorando")
                    continue
                except UnicodeDecodeError:
                    print(f"<-- [ERROR] Paquete con datos binarios corruptos - ignorando")
                    continue

        print(f"SERVIDOR: Archivo completo recibido. Entrando en estado TIME_WAIT (3s)...")
        end_time = time.time() + 3

        while time.time() < end_time:
            try:
                self.socket.settimeout(1)
                packet, _ = self.socket.recvfrom(BUFFER)
                
                try:
                    if b":" in packet:
                        seq_str, chunk = packet.split(b":", 1)
                        seq_received = int(seq_str)
                        print(f"<-- [TIME_WAIT] Paquete tardío seq:{seq_received} ({len(chunk)} bytes)")
                        
                        # Reenviar último ACK
                        if last_correct_seq != -1:
                            ack_msg = f"ACK:{last_correct_seq}"
                            print(f"--> [TIME_WAIT] Reenviando {ack_msg}")
                            self.socket.sendto(ack_msg.encode(), addr)
                    else:
                        print("<-- [TIME_WAIT] Paquete sin formato correcto")
                except (ValueError, UnicodeDecodeError):
                    print("<-- [TIME_WAIT] Paquete tardío corrupto")
                    
            except socket.timeout:
                continue

        print("SERVIDOR: Fase de cierre finalizada.")
        return True, filename
    
    def send_download(self, client_socket: socket.socket, addr, file_path: str):
        try:
            client_socket.settimeout(TIMEOUT)
            filesize = os.path.getsize(file_path)
            with open(file_path, "rb") as file:
                seq_num = 0
                bytes_sent = 0
                while bytes_sent < filesize:
                    chunk = file.read(BUFFER)
                    if not chunk:
                        break
                    packet = f"{seq_num}:".encode() + chunk
                    ack_received = False
                    retries = 0
                    max_retries = 10
                    while not ack_received and retries < max_retries:
                        client_socket.sendto(packet, addr)
                        try:
                            data, _ = client_socket.recvfrom(BUFFER)
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
                        return False
            #client_socket.sendto(b"EOF", addr)
            return True
        except FileNotFoundError:
            print(f"Error: File not found at {file_path}")
            return False

    def receive_download(self, filesize):
        if os.path.isdir(self.args.dst):
            file_path = os.path.join(self.args.dst, self.args.name)
        else:
            file_path = self.args.dst
        print(f"Saving file to: {file_path}")
        with open(file_path, "wb") as file:
            seq_expected = 0
            bytes_received = 0
            while bytes_received < filesize:
                try:
                    packet, _ = self.socket.recvfrom(BUFFER)
                    #if packet == b"EOF":
                    #    break
                    seq_str, chunk = packet.split(b":", 1)
                    seq_received = int(seq_str)
                    if seq_received == seq_expected:
                        file.write(chunk)
                        bytes_received += len(chunk)
                        self.socket.sendto(f"ACK:{seq_received}".encode(), (self.args.host, self.args.port))
                        seq_expected = 1 - seq_expected
                    else:
                        ack_duplicado = 1 - seq_expected
                        print(f"Received duplicate packet {seq_received}, expected {seq_expected}. Resending ACK:{ack_duplicado}")
                        self.socket.sendto(f"ACK:{ack_duplicado}".encode(), (self.args.host, self.args.port))
                except socket.timeout:
                    if bytes_received < filesize:
                        break
                    print("Timeout waiting for packet. The server might have stopped.")
                    return False
                except ValueError:
                    print("Received a malformed packet. Ignoring.")
        print(f"\nFile '{self.args.name}' downloaded successfully to '{self.args.dst}'.")
        return True
    
     