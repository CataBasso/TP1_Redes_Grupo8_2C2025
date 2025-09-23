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
                        handler = SelectiveRepeatProtocol(self.args, self.socket)
                        return handler.send_upload(file_size)
                else:
                    print(f"CLIENTE: El servidor rechazó el saludo con: {response}")
                    return False

            except socket.timeout:
                retries += 1
                current_timeout *= 2
                print(f"CLIENTE: Timeout en saludo, reintentando... ({retries}/{MAX_RETRIES}) con timeout {current_timeout:.2f}s")
        
        print("CLIENTE: No se pudo establecer conexión con el servidor.")
        return False

