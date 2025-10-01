import socket
import time
import logging
from .base_protocol import BaseProtocol

# Constantes
'''TIMEOUTS'''
BASE_TIMEOUT = 0.05
MAX_TIMEOUT = 0.5
'''BUFFER SIZES'''
BUFFER = 1024
RECEIVE_BUFFER = BUFFER + 32
ACK_BUFFER = 64
'''WINDOW AND RETRIES'''
WINDOW_SIZE = 32
MAX_RETRIES = 20

class SelectiveRepeatProtocol(BaseProtocol):
    
    def send_upload(self, file_size):
        """Cliente: Envía archivo al servidor usando Selective Repeat"""
        logging.info(f"CLIENTE: Iniciando envío de {file_size:,} bytes con ventana {WINDOW_SIZE}")
        
        with open(self.args.src, "rb") as file:
            return self._send_file(file, file_size, (self.args.host, self.args.port))

    def receive_upload(self, addr, filename, filesize):
        """Servidor: Recibe archivo del cliente usando Selective Repeat"""
        file_path = self.get_file_path(filename)
        logging.info(f"SERVIDOR: Recibiendo '{filename}' ({filesize:,} bytes)")
        
        with open(file_path, "wb") as file:
            success, bytes_received = self._receive_file(file, filesize, addr)
            
        if success:
            logging.info(f"Archivo {filename} recibido exitosamente: {bytes_received:,} bytes")
        return success, bytes_received

    def send_download(self, addr, filename, filesize):
        """Servidor: Envía archivo al cliente usando Selective Repeat"""
        file_path = self.get_file_path(filename)
        logging.info(f"SERVIDOR: Enviando '{filename}' ({filesize:,} bytes)")
        
        with open(file_path, "rb") as file:
            return self._send_file(file, filesize, addr)

    def receive_download(self, filesize):
        """Cliente: Recibe archivo del servidor usando Selective Repeat"""
        file_path = self._get_download_path()
        logging.info(f"CLIENTE: Recibiendo archivo ({filesize:,} bytes)")
        
        with open(file_path, "wb") as file:
            success, _ = self._receive_file(file, filesize, None)
            return success

    def _send_file(self, file, file_size, dest_addr):
        """Lógica común para enviar archivos con ventana deslizante"""
        base_num = 0
        next_seq_num = 0
        bytes_sent = 0
        pkts = {}  # {seq_num: (packet, sent_time, retries)}
        estimated_rtt = 0.001
        start_time = time.time()

        while bytes_sent < file_size or pkts:
            # FASE 1: Llenar ventana
            next_seq_num, bytes_sent = self._fill_send_window(
                file, file_size, base_num, next_seq_num, bytes_sent, pkts, dest_addr
            )

            # FASE 2: Manejar timeouts
            if not self._handle_timeouts(pkts, estimated_rtt, dest_addr):
                return False

            # FASE 3: Procesar ACKs
            base_num = self._process_acks(pkts, base_num, next_seq_num)
            
            # Mostrar progreso
            if base_num % 20 == 0:
                self.show_progress_bar(base_num * BUFFER, file_size)

            # FASE 4: Verificar fin
            if not pkts and bytes_sent >= file_size:
                break
                
            # Control de flujo
            if len(pkts) >= WINDOW_SIZE:
                time.sleep(0.01)

        self.send_fyn(dest_addr)

        # FASE 5: Limpiar ACKs finales
        self.cleanup_duplicates()
        
        self.show_progress_bar(file_size, file_size)
        elapsed = time.time() - start_time
        logging.info(f"Transferencia completada: {bytes_sent:,} bytes en {elapsed:.1f}s")
        return True

    def _receive_file(self, file, filesize, sender_addr):
        """Lógica común para recibir archivos con ventana deslizante"""
        base_num = 0
        bytes_received = 0
        received_pkts = {}  # {seq_num: chunk}
        start_time = time.time()
        progress_time = start_time
        
        self.socket.settimeout(60.0)

        while True:
            try:
                packet, addr = self.socket.recvfrom(RECEIVE_BUFFER)
                # Parsear paquete
                try:
                    seq_received, chunk = self.parse_packet(packet)
                except ValueError:
                    continue
                
                if seq_received == -99 and chunk == "fin":
                    logging.debug(f"Carga Completada: No se desean recibir ACKS")
                    self.send_fyn(addr)
                    break
                # Procesar según posición en ventana
                if self._is_in_receive_window(seq_received, base_num):
                    # CASO 1: Paquete en ventana
                    bytes_received, base_num = self._handle_in_window_packet(
                        seq_received, chunk, received_pkts, file, bytes_received, base_num
                    )
                    self.send_ack(seq_received, sender_addr or addr)
                    
                elif seq_received < base_num:
                    # CASO 2: Paquete duplicado
                    logging.debug(f"Paquete duplicado seq={seq_received}")
                    self.send_ack(seq_received, sender_addr or addr)

                # CASO 3: Paquete fuera de ventana (muy adelantado) - Ignorar

                # Mostrar progreso
                current_time = time.time()
                if current_time - progress_time > 1:
                    self.show_progress_bar(bytes_received, filesize)
                    progress_time = current_time

            except socket.timeout:
                logging.warning("Timeout - conexión perdida")
                return False, bytes_received
            except (ConnectionResetError, OSError) as e:
                logging.info(f"Conexión interrumpida: {e}")
                return False, bytes_received
            except Exception as e:
                logging.error(f"Error inesperado: {e}")
                continue

        self.show_progress_bar(filesize, filesize)
        elapsed = time.time() - start_time
        logging.info(f"Recepción completada: {bytes_received:,} bytes en {elapsed:.1f}s")
        
        self.cleanup_duplicates()
        return True, bytes_received

    def _fill_send_window(self, file, file_size, base_num, next_seq_num, bytes_sent, pkts, dest_addr):
        """Llena la ventana de envío con nuevos paquetes"""
        while next_seq_num < base_num + WINDOW_SIZE and bytes_sent < file_size:
            chunk = file.read(BUFFER)
            if not chunk:
                break
                
            packet = self.create_packet(next_seq_num, chunk)
            pkts[next_seq_num] = (packet, time.time(), 0)
            
            logging.debug(f"Enviando paquete seq={next_seq_num}")
            self.socket.sendto(packet, dest_addr)
            
            next_seq_num += 1
            bytes_sent += len(chunk)
        return next_seq_num, bytes_sent 

    def _handle_timeouts(self, pkts, estimated_rtt, dest_addr):
        """Maneja timeouts y retransmisiones"""
        current_time = time.time()
        current_timeout = self.calculate_timeout(estimated_rtt, BASE_TIMEOUT, MAX_TIMEOUT, 3.0)

        for seq_num in list(pkts.keys()):
            packet, sent_time, retries = pkts[seq_num]
            
            if current_time - sent_time > current_timeout:
                if retries >= MAX_RETRIES:
                    logging.error(f"Paquete {seq_num} falló después de {MAX_RETRIES} reintentos")
                    return False
                
                logging.debug(f"Reenviando paquete {seq_num} (intento {retries + 1})")
                self.socket.sendto(packet, dest_addr)
                pkts[seq_num] = (packet, current_time, retries + 1)
                
        return True

    def _process_acks(self, pkts, base_num, next_seq_num):
        """Procesa ACKs recibidos y desliza la ventana"""
        self.socket.settimeout(0.05)
        
        try:
            data, _ = self.socket.recvfrom(ACK_BUFFER)
            response = data.decode().strip()
            logging.debug(f"TOTALES ACK ESPERADOS TODAVIA NO RECIBIDOS:{len(pkts)}")
            if response.startswith("ACK:"):
                ack_seq = int(response.split(":")[1])
                
                if ack_seq in pkts:
                    logging.debug(f"ACK válido para seq={ack_seq}")
                    del pkts[ack_seq]
                    
                    # Deslizar ventana
                    while base_num not in pkts and base_num < next_seq_num:
                        base_num += 1
                        
        except socket.timeout:
            pass
        except (ValueError, UnicodeDecodeError, ConnectionResetError, OSError):
            pass
            
        return base_num

    def _is_in_receive_window(self, seq_num, base_num):
        """Verifica si un número de secuencia está en la ventana de recepción"""
        return base_num <= seq_num < base_num + WINDOW_SIZE

    def _handle_in_window_packet(self, seq_received, chunk, received_pkts, file, bytes_received, base_num):
        """Maneja paquetes que están dentro de la ventana de recepción"""
        # Solo procesar si no lo tenemos ya
        if seq_received not in received_pkts:
            received_pkts[seq_received] = chunk
            logging.debug(f"Procesado paquete seq={seq_received}")
        
        # Escribir paquetes consecutivos
        while base_num in received_pkts:
            chunk_to_write = received_pkts[base_num]
            file.write(chunk_to_write)
            bytes_received += len(chunk_to_write)
            logging.debug(f"Escrito paquete seq={base_num}")
            del received_pkts[base_num]
            base_num += 1
            
        return bytes_received, base_num
