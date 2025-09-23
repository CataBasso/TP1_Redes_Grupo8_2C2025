import os
import socket
import time
from lib.stop_and_wait_protocol import StopAndWaitProtocol
from lib.selective_repeat_protocol import SelectiveRepeatProtocol
from lib.logger import get_logger


# Network Configuration
class NetworkConfig:
    TIMEOUT = 10
    BUFFER_SIZE = 1024
    BUFFER_SIZE_SR = 4096
    BUFFER_SIZE_SW = 4096


# Protocol Messages
class Messages:
    UPLOAD_ACK = b"UPLOAD_ACK"
    DOWNLOAD_ACK = b"DOWNLOAD_ACK"
    PROTOCOL_ACK = b"PROTOCOL_ACK"
    FILE_INFO_ACK = b"FILE_INFO_ACK"
    UPLOAD_COMPLETE = b"UPLOAD_COMPLETE"
    ERROR_INVALID_FORMAT = b"ERROR:InvalidFormat"
    ERROR_FILE_NOT_FOUND = b"ERROR:FileNotFound"


# Client Message Types
class ClientMessages:
    UPLOAD_CLIENT = "UPLOAD_CLIENT"
    DOWNLOAD_CLIENT = "DOWNLOAD_CLIENT"


# Protocol Names
class Protocols:
    STOP_AND_WAIT = "stop-and-wait"
    SELECTIVE_REPEAT = "selective-repeat"


# File Information
class FileInfo:
    SEPARATOR = ":"
    DEFAULT_STORAGE = "storage"


# =============================================================================


class ServerProtocol:
    def __init__(self, args):
        self.args = args
        self.main_socket = None
    
    def set_main_socket(self, socket):
        self.main_socket = socket

    def _setup_client_socket(self):
        """Configura el socket temporal del cliente"""
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        client_socket.bind(("", 0))
        client_port = client_socket.getsockname()[1]
        return client_socket, client_port

    def _negotiate_protocol(self, client_socket, addr):
        """Negocia el protocolo con el cliente"""
        retries = 0
        max_retries = 10
        protocol = None
        while retries < max_retries:
            try:
                protocol_data, _ = client_socket.recvfrom(NetworkConfig.BUFFER_SIZE)
                msg = protocol_data.decode()
                if msg in ["stop-and-wait", "selective-repeat"]:
                    print(f"SERVIDOR: Protocolo '{msg}' aceptado. Enviando ACK a {addr}.")
                    client_socket.sendto(Messages.PROTOCOL_ACK, addr)
                    return msg
                else:
                    print(f"SERVIDOR: Mensaje de protocolo inválido de {addr} (contenido: '{msg}'). Ignorando.")
            except socket.timeout:
                retries += 1
                print(f"Timeout esperando el protocolo de {addr}, reintentando {retries}/{max_retries}...")
        raise socket.timeout("Fallo al negociar el protocolo: se agotaron los reintentos.")

    def _validate_file_info(self, file_info):
        """Valida y extrae información del archivo"""
        try:
            parts = file_info.decode().split(FileInfo.SEPARATOR)
            if len(parts) != 2:
                raise ValueError("Invalid file info format")
            filename, filesize_str = parts
            filesize = int(filesize_str)
            if filesize < 0:
                raise ValueError("Invalid file size")
            return filename, filesize
        except (ValueError, UnicodeDecodeError) as e:
            raise ValueError(f"Invalid file info: {e}")

    def handle_upload(self, addr, protocol, filename, filesize):
        logger = get_logger()
        try:
            client_socket, client_port = self._setup_client_socket()
            logger.debug(f"Thread for {addr} on temporary port {client_port}")

            # Enviamos la única confirmación con el nuevo puerto
            response = f"UPLOAD_OK:{client_port}"
            client_socket.sendto(response.encode(), addr)
            logger.verbose_info(f"Sent upload confirmation to {addr} with port {client_port}")
            
            # Obtenemos el manejador de protocolo y procedemos directamente a recibir el archivo
            protocol_handler = self.get_protocol(protocol, self.args, client_socket)
            logger.debug(f"Using protocol handler: {protocol}")
            
            # Llamamos a la versión refactorizada de receive_upload
            success, _ = protocol_handler.receive_upload(addr, filename, filesize)

            if success:
                logger.info(f"File '{filename}' received successfully from {addr}")
            else:
                logger.error(f"File transfer from {addr} failed")

        except Exception as e:
            logger.error(f"Fatal error in thread for {addr}: {e}")

    def handle_download(self, addr, protocol, filename):
        logger = get_logger()
        try:
            # Verificar que el archivo existe
            storage_path = self.args.storage if self.args.storage else FileInfo.DEFAULT_STORAGE
            file_path = os.path.join(storage_path, filename)
            
            if not os.path.isfile(file_path):
                self.main_socket.sendto(b"ERROR:FileNotFound", addr)
                logger.error(f"File '{filename}' does not exist. Sending ERROR to {addr}")
                return

            filesize = os.path.getsize(file_path)
            logger.debug(f"File '{filename}' found ({filesize} bytes)")
            
            client_socket, client_port = self._setup_client_socket()
            logger.debug(f"Temporary socket created on port {client_port}")

            # Enviamos la única confirmación con el nuevo puerto
            response = f"DOWNLOAD_OK:{client_port}:{filesize}"
            
            self.main_socket.sendto(response.encode(), addr)
            logger.verbose_info(f"Handshake sent via main socket: {response}")

            # Obtenemos el manejador de protocolo y mandamos el archivo
            protocol_handler = self.get_protocol(protocol, self.args, client_socket)
            logger.debug(f"Using protocol handler: {protocol}")
            success = protocol_handler.send_download(addr, filename, filesize)
            
            if success:
                logger.info(f"File '{filename}' sent successfully to {addr}")
            else:
                logger.error(f"File transfer to {addr} failed")

        except Exception as e:
            print(f"Error fatal en descarga para {addr}: {e}")

    def get_protocol(self, protocol_name, args, socket):
        """Devuelve el manejador de protocolo correspondiente."""
        protocols = {
            Protocols.STOP_AND_WAIT: StopAndWaitProtocol,
            Protocols.SELECTIVE_REPEAT: SelectiveRepeatProtocol,
        }
        if protocol_name in protocols:
            return protocols[protocol_name](args, socket)
        raise ValueError(f"Protocol {protocol_name} not supported")

    def handle_client(self, addr, data):
        """Maneja la comunicación con un cliente."""
        try:
            message = data.decode()
            
            if message.startswith("UPLOAD_CLIENT:"):
                # Formato: "UPLOAD_CLIENT:protocol:filename:filesize"
                parts = message.split(":")
                protocol = parts[1]
                filename = parts[2]
                filesize = int(parts[3])
                self.handle_upload(addr, protocol, filename, filesize)
                
            elif message.startswith("DOWNLOAD_CLIENT:"):
                # Formato: "DOWNLOAD_CLIENT:protocol:filename"
                parts = message.split(":")
                protocol = parts[1]
                filename = parts[2]
                self.handle_download(addr, protocol, filename)
                
            else:
                print(f"Unknown client message from {addr}: {message}")
                
        except (ValueError, IndexError) as e:
            print(f"Invalid message format from {addr}: {data.decode()} - {e}")
