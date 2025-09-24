import socket
import os
import time
import logging

BUFFER = 1024
RECV_BUFFER = 2048
TIMEOUT = 0.5

class BaseProtocol:
    """Clase base con funcionalidad común para protocolos"""
    
    def __init__(self, args, client_socket: socket.socket):
        self.args = args
        self.socket = client_socket

    def show_progress_bar(self, current, total, bar_length=50):
        """Muestra una barra de progreso ASCII"""
        progress = min(current / total, 1.0)
        filled_length = int(bar_length * progress)
        bar = '█' * filled_length + '-' * (bar_length - filled_length)
        percent = progress * 100
        print(f'\r[{bar}] {percent:.1f}% ({current}/{total})', end='', flush=True)
        if progress >= 1.0:
            print()

    def update_rtt(self, estimated_rtt, sample_rtt):
        """Actualiza RTT estimado usando promedio exponencial"""
        if estimated_rtt is None:
            return sample_rtt
        return (0.7 * estimated_rtt) + (0.3 * sample_rtt)

    def calculate_timeout(self, estimated_rtt, min_timeout, max_timeout, multiplier=2.5):
        """Calcula timeout basado en RTT"""
        if estimated_rtt is None:
            return min_timeout
        timeout = max(estimated_rtt * multiplier, min_timeout)
        return min(timeout, max_timeout)

    def handle_progress(self, packet_count, bytes_processed, total_bytes, interval=100):
        """Maneja mostrar progreso cada cierto intervalo"""
        if packet_count == 1 or packet_count % interval == 0:
            self.show_progress_bar(bytes_processed, total_bytes)

    def parse_packet(self, packet):
        """Parsea paquete en formato 'seq:data'"""
        if b":" not in packet:
            raise ValueError("Paquete sin formato ':'")
        seq_str, chunk = packet.split(b":", 1)
        return int(seq_str), chunk

    def create_packet(self, seq_num, chunk):
        """Crea paquete en formato 'seq:data'"""
        return f"{seq_num}:".encode() + chunk

    def send_ack(self, seq_num, addr):
        """Envía ACK para número de secuencia"""
        ack_msg = f"ACK:{seq_num}".encode()
        self.socket.sendto(ack_msg, addr)
        logging.debug(f"ACK enviado para seq={seq_num}")

    def is_expected_ack(self, response, expected_seq):
        """Verifica si el ACK recibido es el esperado"""
        return response.strip() == f"ACK:{expected_seq}"

    def get_file_path(self, filename, storage_dir="storage"):
        """Obtiene ruta completa del archivo"""
        storage_path = getattr(self.args, 'storage', None) or storage_dir
        os.makedirs(storage_path, exist_ok=True)
        return os.path.join(storage_path, filename)

    def cleanup_duplicates(self, timeout_duration=2):
        """Limpia paquetes duplicados al final de transferencia"""
        end_time = time.time() + timeout_duration
        while time.time() < end_time:
            try:
                self.socket.settimeout(TIMEOUT)
                self.socket.recvfrom(BUFFER)
            except:
                continue

    def _get_download_path(self):
        """Obtiene ruta de descarga"""
        if hasattr(self.args, 'dst') and os.path.isdir(self.args.dst):
            return os.path.join(self.args.dst, self.args.name)
        return getattr(self.args, 'dst', self.args.name)
    
    def cleanup_duplicates(self, timeout_duration=2):
        """Limpia paquetes duplicados al final de transferencia"""
        end_time = time.time() + timeout_duration
        while time.time() < end_time:
            try:
                self.socket.settimeout(0.2)
                self.socket.recvfrom(RECV_BUFFER)
            except:
                continue