#Selective Repeat es un protocolo de ventana deslizante que permite:

# - Múltiples paquetes en vuelo (vs Stop-and-Wait que es 1 por vez)
# - ACKs individuales para cada paquete
# - Retransmisión selectiva solo de paquetes perdidos (no todos)
# ------------------ LADO CLIENTE --------------------- send_upload()
# --- FASE 1 --- Llenar ventana
# Envía:  [0] [1] [2] [3] [4] [5] [6] [7] ... hasta WINDOW_SIZE
# Estado: base=0, next=32, pkts={0,1,2,...,31}

# --- FASE 2 --- Manejar timeouts y retransmisiones
# Ventana: [0] [1] [2] [3] [4] [5] [6] [7]
# Timeout:  ✓   ✗   ✓   ✓   ✗   ✓   ✓   ✓
# Reenvía:       1            4              Solo paquetes 1 y 4

# --- FASE 3 --- Procesar ACKs
# Antes:  base=0, pkts={0,1,2,3,4,5,6,7}
# ACK:3   base=0, pkts={0,1,2,4,5,6,7}     # Elimina 3
# ACK:0   base=0, pkts={1,2,4,5,6,7}       # Elimina 0
#         base=1, pkts={2,4,5,6,7}          # Avanza base (0 ya no existe)
#         base=2, pkts={4,5,6,7}            # Avanza base (1 ya no existe)  
#         base=4, pkts={4,5,6,7}            # Para (2 no confirmado)
# Ahora puede enviar paquetes [32] [33] [34] [35]
# porque la ventana se desplazó: [4,5,6,7,32,33,34,35]

# --- FASE 4 --- Verificar si terminamos
# --- FASE 5 --- Limpiar ACKs duplicados al final

# ------------------ LADO SERVIDOR --------------------- receive_upload()
# --- CASO 1 --- Recibir paquetes y manejar ventana
# Estado inicial: base=0, received_pkts={}
# Recibe paquete 2: received_pkts={2: chunk2}  # No escribe (falta 0,1)
# Recibe paquete 0: received_pkts={0: chunk0, 2: chunk2}
#                   Escribe chunk0, base=1      # Puede escribir 0
#                   received_pkts={2: chunk2}   # Queda 2 esperando
# Recibe paquete 1: received_pkts={1: chunk1, 2: chunk2}
#                   Escribe chunk1, base=2      # Puede escribir 1
#                   Escribe chunk2, base=3      # También puede escribir 2!
#                   received_pkts={}            # Buffer vacío
# --- CASO 2 --- Paquete duplicado (ya procesado)
# Si recibo un paquete que ya procese, reenvio ACK por si se perdio
# --- CASO 3 --- Paquete fuera de ventana (muy adelantado)
# Si recibo un paquete fuera de la ventana que estoy esperando, lo ignoro (NO envio ACK)


import os
import socket
import time
import logging

BUFFER = 1024
RECEIVE_BUFFER = BUFFER + 32
ACK_BUFFER = 64

WINDOW_SIZE = 32

BASE_TIMEOUT = 0.05
MAX_TIMEOUT = 0.5

MAX_RETRIES = 20

class SelectiveRepeatProtocol:
    def __init__(self, args, sock: socket.socket):
        self.args = args
        self.socket = sock

    def show_progress_bar(self, current, total, bar_length=50):
        """Muestra una barra de progreso ASCII"""
        progress = min(current / total, 1.0)
        filled_length = int(bar_length * progress)
        bar = '█' * filled_length + '-' * (bar_length - filled_length)
        percent = progress * 100
        print(f'\r[{bar}] {percent:.1f}% ({current}/{total})', end='', flush=True)
        if progress >= 1.0:
            print() 

    def send_upload(self, file_size):
        """Cliente: Envía archivo con ventana deslizante"""
        try:
            with open(self.args.src, "rb") as file:
                base_num = 0 # Primer paquete sin confirmar
                next_seq_num = 0 # Próximo paquete a enviar
                bytes_sent = 0 
                pkts = {}  # Diccionario: {seq_num: (packet, sent_time, retries)}
                estimated_rtt = 0.001

                logging.info(f"CLIENTE: Enviando archivo ({file_size:,} bytes) con ventana {WINDOW_SIZE}")
                start_time = time.time()

                while bytes_sent < file_size or pkts:
                    # FASE 1: Llenar ventana
                    while next_seq_num < base_num + WINDOW_SIZE and bytes_sent < file_size:
                        chunk = file.read(BUFFER)
                        if not chunk:
                            break
                        packet = f"{next_seq_num}:".encode() + chunk # Formato: "next_seq_num:datos"
                        pkts[next_seq_num] = (packet, time.time(), 0) #  guardar con timestamp
                        logging.debug(f"Enviando paquete seq={next_seq_num}, bytes={len(packet)}")
                        self.socket.sendto(packet, (self.args.host, self.args.port))
                        next_seq_num += 1
                        bytes_sent += len(chunk)

                    # FASE 2: Manejar timeouts y retransmisiones
                    current_time = time.time()
                    current_timeout = max(estimated_rtt * 3, BASE_TIMEOUT)
                    current_timeout = min(current_timeout, MAX_TIMEOUT)

                    for seq_num in list(pkts.keys()):
                        packet, sent_time, retries = pkts[seq_num]
                        if current_time - sent_time > current_timeout: # Si se envio hace mucho, retransmitir
                            if retries >= MAX_RETRIES:  # Si supera reintentos, abortar
                                logging.error(f"Paquete {seq_num} falló después de {MAX_RETRIES} reintentos")
                                return False
                            logging.debug(f"Timeout para seq={seq_num}, reenvío intento {retries + 1}")
                            logging.warning(f"Reenviando paquete {seq_num} (intento {retries + 1})")
                            self.socket.sendto(packet, (self.args.host, self.args.port))
                            pkts[seq_num] = (packet, current_time, retries + 1)


                    # FASE 3: Procesar ACKs
                    self.socket.settimeout(0.05)
                    
                    try:
                        data, addr = self.socket.recvfrom(ACK_BUFFER)
                        response = data.decode().strip()
                        logging.debug(f"Recibido ACK de {addr}: {response}")
                        if response.startswith("ACK:"):
                            ack_seq = int(response.split(":")[1]) 
                            logging.debug(f"Procesando ACK para seq={ack_seq}")
                            if ack_seq in pkts:
                                logging.debug(f"ACK válido para seq={ack_seq}, eliminando de pkts")
                                del pkts[ack_seq]
                                # ← DESLIZAR VENTANA (base avanza)
                                while base_num not in pkts and base_num < next_seq_num:
                                    base_num += 1
                                # Mostrar progreso
                                if base_num % 2 == 0:
                                    self.show_progress_bar(base_num * BUFFER, file_size)
                        else:
                            logging.debug(f"ACK no reconocido: {response}")
                    except socket.timeout:
                        logging.debug("Timeout esperando ACK")
                        pass
                    except (ValueError, UnicodeDecodeError):
                        logging.warning("ACK malformado - ignorando")
                        continue

                    # FASE 4: Verificar si terminamos
                    if not pkts and bytes_sent >= file_size:
                        logging.info(f"[UPLOAD COMPLETADO] Archivo enviado completamente: {bytes_sent:,} bytes")
                        break
                    
                    # ← CONTROL DE FLUJO: Pausa si hay muchos paquetes sin confirmar
                    if len(pkts) >= WINDOW_SIZE:    
                        time.sleep(0.01) 
                
                # FASE 5: Limpiar ACKs duplicados al final
                end_time = time.time() + 2
                while time.time() < end_time:
                    try:
                        self.socket.settimeout(0.2)
                        data, _ = self.socket.recvfrom(64)
                    except:
                        break
                
                self.show_progress_bar(file_size, file_size)
                logging.info(f"\n--- UPLOAD COMPLETADO ---")
                elapsed_total = time.time() - start_time
                logging.info(f"Archivo enviado: {bytes_sent:,} bytes en {elapsed_total:.1f}s")
                return True

        except Exception as e:
            logging.error(f"[ERROR]: {e}")
            return False

    def receive_upload(self, addr, filename, filesize):
        """Servidor: Recibe archivo con ventana deslizante"""
        storage_path = self.args.storage if self.args.storage else "storage"
        os.makedirs(storage_path, exist_ok=True)
        file_path = os.path.join(storage_path, filename)

        logging.info(f"SERVIDOR: Recibiendo '{filename}' ({filesize:,} bytes)")

        with open(file_path, "wb") as file:
            base_num = 0
            bytes_received = 0
            received_pkts = {}  # {seq_num: chunk} - Buffer para paquetes fuera de orden
            
            start_time = time.time()
            self.socket.settimeout(60.0)
            
            while bytes_received < filesize:
                try:
                    packet, client_addr = self.socket.recvfrom(RECEIVE_BUFFER)
                    logging.debug(f"Recibido paquete de {client_addr}: {packet[:50]}... (total {len(packet)} bytes)")

                    # Validar formato del paquete
                    if b":" not in packet:
                        continue

                    seq_str, chunk = packet.split(b":", 1)
                    seq_received = int(seq_str)

                    # ← CASO 1: Paquete dentro de la ventana de recepción
                    if base_num <= seq_received < base_num + WINDOW_SIZE:
                        logging.debug(f"Recibido paquete seq={seq_received}, bytes={len(chunk)} dentro de ventana [{base_num}, {base_num + WINDOW_SIZE - 1}]")
                        # Solo procesar si no lo tenemos ya (evitar duplicados)
                        if seq_received not in received_pkts:
                            received_pkts[seq_received] = chunk
                            logging.debug(f"Paquete procesado seq={seq_received}, bytes={len(chunk)}")
                        # ← ESCRIBIR PAQUETES CONSECUTIVOS (ventana deslizante)
                        while base_num in received_pkts:
                            chunk_to_write = received_pkts[base_num]
                            file.write(chunk_to_write)
                            bytes_received += len(chunk_to_write)
                            logging.debug(f"Escribiendo paquete seq={base_num}, bytes={len(chunk_to_write)}")
                            del received_pkts[base_num]
                            base_num += 1
                        # ← ENVIAR ACK (con rate limiting para evitar saturación)
                        ack_msg = f"ACK:{seq_received}".encode()
                        logging.debug(f"Enviando ACK para seq={seq_received}")
                        self.socket.sendto(ack_msg, client_addr)
                    # ← CASO 2: Paquete anterior (duplicado)
                    elif seq_received < base_num:
                        logging.debug(f"Recibido paquete duplicado seq={seq_received}, reenviando ACK")
                        ack_msg = f"ACK:{seq_received}".encode()
                        self.socket.sendto(ack_msg, client_addr)
 
                    # ← MOSTRAR PROGRESO cada 2 segundos
                    if time.time() - start_time > 1:
                        self.show_progress_bar(bytes_received, filesize)

                    # ← VERIFICAR SI TERMINAMOS
                    if bytes_received >= filesize:
                        logging.info(f"SERVIDOR: Archivo completo recibido: {bytes_received:,} bytes")
                        break

                except socket.timeout:
                    return False, 0
                
                except Exception as e:
                    logging.error(f"SERVIDOR: Error inesperado: {e}")
                    continue

            # ← LIMPIAR ACKs FINALES para paquetes duplicados
            end_time = time.time() + 2
            while time.time() < end_time:
                try:
                    self.socket.settimeout(0.2)
                    packet, client_addr = self.socket.recvfrom(RECEIVE_BUFFER)
                    
                    if b":" in packet:
                        try:
                            seq_str, _ = packet.split(b":", 1)
                            seq_received = int(seq_str)
                            ack_msg = f"ACK:{seq_received}".encode()
                            self.socket.sendto(ack_msg, client_addr)
                            logging.debug(f"Resent ACK for final packet seq={seq_received}")
                        except (ValueError, UnicodeDecodeError):
                            continue
                            
                except socket.timeout:
                    break
                except:
                    break

            # ← ESTADÍSTICAS FINALES
            elapsed_total = time.time() - start_time
            logging.info(f"\n--- RECEPCIÓN COMPLETADA ---")
            logging.info(f"Archivo: {filename} ({bytes_received:,} bytes)")
            logging.info(f"Tiempo: {elapsed_total:.1f}s")
            return True, bytes_received

    def recieve_download(self, filesize):
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
        if os.path.isdir(self.args.dst):
            file_path = os.path.join(self.args.dst, self.args.name)
        else:
            file_path = self.args.dst

        logging.info(f"Saving file to: {file_path}")

        with open(file_path, "wb") as file:
            window_size = (
                4  # cant_pkt_env / 2 -> #cant_pkt_env = file_size / channel_size
            )
            base_num = 0
            bytes_sent = 0
            pkts = {}  # Diccionario: {seq_num: (packet, sent_time)}
            while bytes_sent < filesize:
                try:
                    packet, _ = self.socket.recvfrom(4096)
                    seq_str, chunk = packet.split(b":", 1)
                    seq_received = int(seq_str)

                    if base_num <= seq_received < base_num + window_size:
                        if seq_received not in pkts:
                            logging.debug(f"Recibido paquete seq={seq_received}, bytes={len(chunk)} dentro de ventana [{base_num}, {base_num + window_size - 1}]")
                            file.write(chunk)
                            bytes_sent += len(chunk)
                            pkts[seq_received] = (packet, None)
                        logging.debug(f"Enviando ACK para seq={seq_received}")
                        self.socket.sendto(
                            f"ACK:{seq_received}".encode(), (self.args.host, self.args.port)
                        )
                        while base_num in pkts:
                            logging.debug(f"Deslizando ventana, eliminando seq={base_num}")
                            del pkts[base_num]
                            base_num += 1
                    else:
                        logging.warning(
                            f"Received out-of-window packet {seq_received}, expected window [{base_num}, {base_num + window_size - 1}]. Ignoring."
                        )
                        logging.debug(f"Paquete fuera de ventana seq={seq_received}, ignorado")
                        if seq_received < base_num:
                            logging.debug(f"Recibido paquete antiguo seq={seq_received}, reenviando ACK")
                            self.socket.sendto(
                                f"ACK:{seq_received}".encode(), (self.args.host, self.args.port)
                            )
                            logging.info(f"Resent ACK for old packet {seq_received}.")

                except socket.timeout:
                    logging.warning("Timeout waiting for packet. The server might have stopped.")
                    return False
                except ValueError:
                    logging.error("Received a malformed packet. Ignoring.")
                    return False

        logging.info(f"\nFile '{self.args.name}' downloaded successfully to '{self.args.dst}'.")
        return True
