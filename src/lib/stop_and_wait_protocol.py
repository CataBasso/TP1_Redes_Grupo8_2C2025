import socket
import time
import logging

from .base_protocol import BaseProtocol

# Constantes
'''TIMEOUTS'''
CLIENT_TIMEOUT_START = 0.02
CLIENT_TIMEOUT_MAX = 0.5
SERVER_TIMEOUT = 30.0
'''BUFFER SIZES'''
BUFFER = 800
BUFFER_ACK = 64
'''RETRIES'''
MAX_RETRIES = 20

class StopAndWaitProtocol(BaseProtocol):
    
    def send_upload(self, file_size):
        """Envía archivo al servidor usando Stop-and-Wait"""
        logging.info(f"CLIENTE: Iniciando envío de {file_size:,} bytes")
        
        with open(self.args.src, "rb") as file:
            return self._send_file(file, file_size, (self.args.host, self.args.port))

    def receive_upload(self, addr, filename, filesize):
        """Recibe archivo del cliente usando Stop-and-Wait"""
        file_path = self.get_file_path(filename)
        logging.info(f"SERVIDOR: Recibiendo '{filename}' ({filesize:,} bytes)")
        
        with open(file_path, "wb") as file:
            success = self._receive_file(file, filesize, addr)
            
        if success:
            logging.info(f"Archivo {filename} recibido exitosamente")
        return success, filename

    def send_download(self, addr, filename, filesize):
        """Envía archivo al cliente usando Stop-and-Wait"""
        file_path = self.get_file_path(filename)
        logging.info(f"SERVIDOR: Enviando '{filename}' ({filesize:,} bytes)")
        
        with open(file_path, "rb") as file:
            return self._send_file(file, filesize, addr)

    def receive_download(self, filesize):
        """Recibe archivo del servidor usando Stop-and-Wait"""
        file_path = self._get_download_path()
        logging.info(f"CLIENTE: Recibiendo archivo ({filesize:,} bytes)")
        
        with open(file_path, "wb") as file:
            return self._receive_file(file, filesize, None)

    def _send_file(self, file, file_size, dest_addr):
        """Lógica común para enviar archivos"""
        seq_num = 0
        bytes_sent = 0
        estimated_rtt = None
        current_timeout = CLIENT_TIMEOUT_START
        packet_count = 0
        start_time = time.time()

        while bytes_sent < file_size:
            packet_count += 1
            chunk = file.read(min(BUFFER, file_size - bytes_sent))
            if not chunk:
                break

            self.handle_progress(packet_count, bytes_sent, file_size)
            
            if not self._send_packet_reliable(seq_num, chunk, dest_addr, estimated_rtt, current_timeout):
                return False
                
            bytes_sent += len(chunk)
            seq_num = 1 - seq_num

        self.show_progress_bar(file_size, file_size)
        elapsed = time.time() - start_time
        logging.info(f"Transferencia completada: {bytes_sent:,} bytes en {elapsed:.1f}s")
        return True

    def _receive_file(self, file, filesize, sender_addr):
        """Lógica común para recibir archivos"""
        seq_expected = 0
        bytes_received = 0
        last_correct_seq = -1
        packet_count = 0
        start_time = time.time()
        
        self.socket.settimeout(SERVER_TIMEOUT)

        while bytes_received < filesize:
            try:
                packet, addr = self.socket.recvfrom(BUFFER + 100)
                packet_count += 1
                
                seq_received, chunk = self.parse_packet(packet)
                
                self.handle_progress(packet_count, bytes_received + len(chunk), filesize, 200)

                if seq_received == seq_expected:
                    file.write(chunk)
                    bytes_received += len(chunk)
                    last_correct_seq = seq_received
                    self.send_ack(seq_received, sender_addr or addr)
                    seq_expected = 1 - seq_expected
                    
                    if bytes_received >= filesize:
                        break
                else:
                    # Paquete duplicado
                    if last_correct_seq != -1:
                        self.send_ack(last_correct_seq, sender_addr or addr)

            except socket.timeout:
                logging.warning("Timeout - conexión perdida")
                return False
            except (ValueError, UnicodeDecodeError) as e:
                logging.error(f"Paquete corrupto: {e}")
                continue

        self.show_progress_bar(filesize, filesize)
        elapsed = time.time() - start_time
        logging.info(f"Recepción completada: {bytes_received:,} bytes en {elapsed:.1f}s")
        
        self.cleanup_duplicates()
        return True

    def _send_packet_reliable(self, seq_num, chunk, dest_addr, estimated_rtt, current_timeout):
        """Envía un paquete de forma confiable con reintentos"""
        packet = self.create_packet(seq_num, chunk)
        retries = 0
        
        while retries < MAX_RETRIES:
            # FASE 1: ENVIO
            self.socket.sendto(packet, dest_addr)
            send_time = time.monotonic()
            
            try:
                # FASE 2: ESPERA ACK
                self.socket.settimeout(current_timeout)
                data, _ = self.socket.recvfrom(BUFFER_ACK)
                recv_time = time.monotonic()
                
                # FASE 3: MEDICION DE RTT Y ACTUALIZACION TIMEOUT
                sample_rtt = recv_time - send_time
                estimated_rtt = self.update_rtt(estimated_rtt, sample_rtt)
                current_timeout = self.calculate_timeout(estimated_rtt, CLIENT_TIMEOUT_START, CLIENT_TIMEOUT_MAX)
                
                # FASE 4: VERIFICACION DE ACK
                response = data.decode()
                if self.is_expected_ack(response, seq_num):
                    return True
                    
            except socket.timeout:
                # FASE 5: RETRANSMISION
                retries += 1
                current_timeout = min(current_timeout * 1.3, CLIENT_TIMEOUT_MAX)
                
        logging.error(f"Paquete {seq_num} falló después de {MAX_RETRIES} reintentos")
        return False
