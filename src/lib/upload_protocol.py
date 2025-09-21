import socket
import os
from lib.selective_repeat_protocol import SelectiveRepeatProtocol
from lib.stop_and_wait_protocol import StopAndWaitProtocol

TIMEOUT = 2
BUFFER = 1024
MAX_RETRIES = 10

class UploadProtocol:
    def __init__(self, args):
        self.args = args
        self.socket = None

    def establish_connection(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.settimeout(TIMEOUT)
        print(f"CLIENTE: Preparado para conectar con el servidor en {self.args.host}:{self.args.port}")

        retries = 0
        while retries < MAX_RETRIES:
            print(f"CLIENTE: (Intento {retries + 1}/{MAX_RETRIES}) Enviando UPLOAD_CLIENT...")
            self.socket.sendto(b"UPLOAD_CLIENT", (self.args.host, self.args.port))
            try:
                print("CLIENTE: Esperando ACK y nuevo puerto del servidor...")
                data, addr = self.socket.recvfrom(BUFFER)
                response = data.decode()

                # Verificamos si la respuesta es la que esperamos y la procesamos
                if response.startswith("UPLOAD_ACK:"):
                    parts = response.split(":")
                    new_port = int(parts[1])
                    print(f"CLIENTE: ACK recibido. Servidor asignó el puerto {new_port}. Conexión establecida.")
                    self.args.port = new_port
                    return True
                else:
                    print(f"CLIENTE: Error - Respuesta inesperada del servidor. Se recibió: {response}")
                    return False
                    
            except socket.timeout:
                retries += 1
                print(f"CLIENTE: Timeout! El servidor no respondió (Intento {retries}/{MAX_RETRIES}). Reintentando...")

        print("CLIENTE: Error - Se alcanzó el máximo de reintentos. Terminando.")
        return False
    
    def send_protocol_info(self, protocol):
        retries = 0
        
        while retries < MAX_RETRIES:
            self.socket.sendto(protocol.encode(), (self.args.host, self.args.port))
            try:
                data, addr = self.socket.recvfrom(BUFFER)
                if data.decode() == "PROTOCOL_ACK":
                    print("CLIENTE: El servidor confirmó el protocolo.")
                    return True
                else:
                    print(f"El servidor no confirmó la elección del protocolo. Recibido: {data.decode()}")
                    return False
            except socket.timeout:
                retries += 1
                print(f"Sin respuesta del servidor al enviar protocolo, reintentando... {retries}/{MAX_RETRIES}")
                
        print("Se alcanzó el máximo de reintentos para la elección de protocolo.")
        return False

    def send_file_info(self):
        retries = 0
        if not os.path.isfile(self.args.src):
            print(f"El archivo de origen {self.args.src} no existe.")
            return None

        file_size = os.path.getsize(self.args.src)
        print(f"Subiendo archivo {self.args.name} (tamaño: {file_size} bytes).")
        file_info = f"{self.args.name}:{file_size}"

        current_timeout = TIMEOUT

        while retries < MAX_RETRIES:
            self.socket.sendto(file_info.encode(), (self.args.host, self.args.port))

            try:
                self.socket.settimeout(current_timeout)
                data, addr = self.socket.recvfrom(BUFFER)
                if data.decode() == "FILE_INFO_ACK":
                    print("Servidor confirmó la información del archivo.")
                    # Reseteamos el timeout para futuras operaciones
                    self.socket.settimeout(TIMEOUT) 
                    return file_size
                else:
                    print(f"El servidor respondió de forma inesperada: {data.decode()}")
                    self.socket.settimeout(TIMEOUT)
                    return None
            except socket.timeout:
                retries += 1
                current_timeout *= 2 
                print(f"Sin respuesta del servidor, reintentando... ({retries}/{MAX_RETRIES}) con nuevo timeout de {current_timeout:.2f}s")

        print("Se alcanzó el máximo de reintentos al enviar la info del archivo.")
        self.socket.settimeout(TIMEOUT)    
        return False

    def upload_file(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        protocol = self.args.protocol if self.args.protocol else "stop-and-wait"
        if not os.path.isfile(self.args.src):
            print(f"Error: El archivo de origen {self.args.src} no existe.")
            return False
        file_size = os.path.getsize(self.args.src)
        
        handshake_msg = f"UPLOAD_CLIENT:{protocol}:{self.args.name}:{file_size}"
        print(f"CLIENTE: Enviando saludo: {handshake_msg}")

        retries = 0
        current_timeout = TIMEOUT
        while retries < MAX_RETRIES:
            self.socket.sendto(handshake_msg.encode(), (self.args.host, self.args.port))
            try:
                self.socket.settimeout(current_timeout)
                data, _ = self.socket.recvfrom(BUFFER)
                response = data.decode()

                if response.startswith("UPLOAD_OK:"):
                    new_port = int(response.split(":")[1])
                    print(f"CLIENTE: Saludo aceptado. Servidor asignó puerto {new_port}.")
                    self.args.port = new_port
                    
                    if protocol == "stop-and-wait":
                        handler = StopAndWaitProtocol(self.args, self.socket)
                        return handler.send_upload(file_size)
                    elif protocol == "selective-repeat":
                        # ... selective repeat ...
                        pass
                else:
                    print(f"CLIENTE: El servidor rechazó el saludo con: {response}")
                    return False

            except socket.timeout:
                retries += 1
                current_timeout *= 2
                print(f"CLIENTE: Timeout en saludo, reintentando... ({retries}/{MAX_RETRIES}) con timeout {current_timeout:.2f}s")
        
        print("CLIENTE: No se pudo establecer conexión con el servidor.")
        return False

