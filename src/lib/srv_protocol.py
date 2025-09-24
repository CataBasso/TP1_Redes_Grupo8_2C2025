import os
import socket
import time
import logging
from lib.stop_and_wait_protocol import StopAndWaitProtocol
from lib.selective_repeat_protocol import SelectiveRepeatProtocol


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
        logging.debug(f"Seteando main_socket: {socket}")
        self.main_socket = socket

    def _setup_client_socket(self):
        """Configura el socket temporal del cliente"""
        logging.debug("Creando socket temporal para cliente")
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        client_socket.bind(("", 0))
        client_port = client_socket.getsockname()[1]
        logging.debug(f"Socket temporal creado en puerto {client_port}")
        return client_socket, client_port

    def _negotiate_protocol(self, client_socket, addr):
        """Negocia el protocolo con el cliente"""
        retries = 0
        max_retries = 10
        protocol = None
        logging.debug(f"Negociando protocolo con {addr}")
        while retries < max_retries:
            try:
                protocol_data, _ = client_socket.recvfrom(NetworkConfig.BUFFER_SIZE)
                msg = protocol_data.decode()
                logging.debug(f"Recibido mensaje de protocolo: '{msg}' de {addr}")
                if msg in ["stop-and-wait", "selective-repeat"]:
                    logging.info(f"SERVIDOR: Protocolo '{msg}' aceptado. Enviando ACK a {addr}.")
                    client_socket.sendto(Messages.PROTOCOL_ACK, addr)
                    logging.debug(f"ACK de protocolo enviado a {addr}")
                    return msg
                else:
                    logging.warning(f"SERVIDOR: Mensaje de protocolo inválido de {addr} (contenido: '{msg}'). Ignorando.")
            except socket.timeout:
                retries += 1
                logging.debug(f"Timeout esperando protocolo de {addr}, intento {retries}/{max_retries}")
                logging.warning(f"Timeout esperando el protocolo de {addr}, reintentando {retries}/{max_retries}...")
        logging.debug(f"Fallo al negociar protocolo con {addr} tras {max_retries} intentos")
        raise socket.timeout("Fallo al negociar el protocolo: se agotaron los reintentos.")

    def _validate_file_info(self, file_info):
        """Valida y extrae información del archivo"""
        logging.debug(f"Validando file_info: {file_info}")
        try:
            parts = file_info.decode().split(FileInfo.SEPARATOR)
            logging.debug(f"Partes extraídas: {parts}")
            if len(parts) != 2:
                logging.debug("Formato inválido de file_info")
                raise ValueError("Invalid file info format")
            filename, filesize_str = parts
            filesize = int(filesize_str)
            if filesize < 0:
                logging.debug("Tamaño de archivo negativo")
                raise ValueError("Invalid file size")
            logging.debug(f"File info validado: filename={filename}, filesize={filesize}")
            return filename, filesize
        except (ValueError, UnicodeDecodeError) as e:
            logging.debug(f"Error validando file_info: {e}")
            raise ValueError(f"Invalid file info: {e}")

    def handle_upload(self, addr, protocol, filename, filesize):
        try:
            logging.debug(f"Iniciando handle_upload para {addr}, protocolo={protocol}, filename={filename}, filesize={filesize}")
            client_socket, client_port = self._setup_client_socket()
            logging.info(f"SERVIDOR: Hilo para {addr} en puerto temporal {client_port}")

            response = f"UPLOAD_OK:{client_port}"
            logging.debug(f"Enviando handshake de upload: {response} a {addr}")
            client_socket.sendto(response.encode(), addr)

            protocol_handler = self.get_protocol(protocol, self.args, client_socket)
            logging.debug(f"Instanciado handler de protocolo: {protocol_handler}")
            success, _ = protocol_handler.receive_upload(addr, filename, filesize)
            logging.debug(f"Resultado de receive_upload: {success}")
            if success:
                logging.info(f"File '{filename}' received successfully from {addr}")
            else:
                logging.error(f"File transfer from {addr} failed.")
        except Exception as e:
            logging.critical(f"Error fatal en el hilo de {addr}: {e}")

    def handle_download(self, addr, protocol, filename):
        try:
            logging.debug(f"Iniciando handle_download para {addr}, protocolo={protocol}, filename={filename}")

            storage_path = self.args.storage if self.args.storage else FileInfo.DEFAULT_STORAGE
            file_path = os.path.join(storage_path, filename)
            logging.debug(f"Ruta de archivo a enviar: {file_path}")
            if not os.path.isfile(file_path):
                logging.debug(f"Archivo '{filename}' no existe, enviando error a {addr}")
                self.main_socket.sendto(b"ERROR:FileNotFound", addr)
                logging.warning(f"SERVIDOR: El archivo '{filename}' no existe. Enviando ERROR a {addr}.")
                return
            filesize = os.path.getsize(file_path)
            logging.info(f"SERVIDOR: Archivo '{filename}' encontrado ({filesize} bytes).")
            client_socket, client_port = self._setup_client_socket()
            logging.info(f"SERVIDOR: Socket temporal creado en puerto {client_port}")

            response = f"DOWNLOAD_OK:{client_port}:{filesize}"
            logging.debug(f"Enviando handshake de download: {response} a {addr}")
            self.main_socket.sendto(response.encode(), addr)
            logging.info(f"SERVIDOR: Handshake enviado por socket principal: {response}")

            protocol_handler = self.get_protocol(protocol, self.args, client_socket)
            logging.debug(f"Instanciado handler de protocolo: {protocol_handler}")
            success = protocol_handler.send_download(addr, filename, filesize)
            logging.debug(f"Resultado de send_download: {success}")
            if success:
                logging.info(f"File '{filename}' sent successfully to {addr}")
            else:
                logging.error(f"File transfer to {addr} failed.")
        except Exception as e:
            logging.critical(f"Error fatal en descarga para {addr}: {e}")

    def get_protocol(self, protocol_name, args, socket):
        """Devuelve el manejador de protocolo correspondiente."""
        logging.debug(f"get_protocol llamado con protocol_name={protocol_name}")
        protocols = {
            Protocols.STOP_AND_WAIT: StopAndWaitProtocol,
            Protocols.SELECTIVE_REPEAT: SelectiveRepeatProtocol,
        }
        if protocol_name in protocols:
            logging.debug(f"Protocolo encontrado: {protocol_name}, instanciando handler")
            return protocols[protocol_name](args, socket)
        logging.debug(f"Protocolo no soportado: {protocol_name}")
        raise ValueError(f"Protocol {protocol_name} not supported")

    def handle_client(self, addr, data):
        """Maneja la comunicación con un cliente."""
        try:
            logging.debug(f"handle_client llamado con addr={addr}, data={data}")
            message = data.decode()
            logging.debug(f"Mensaje decodificado: {message}")
            if message.startswith("UPLOAD_CLIENT:"):
                # Formato: "UPLOAD_CLIENT:protocol:filename:filesize"
                parts = message.split(":")
                logging.debug(f"Partes de mensaje UPLOAD_CLIENT: {parts}")
                protocol = parts[1]
                filename = parts[2]
                filesize = int(parts[3])
                self.handle_upload(addr, protocol, filename, filesize)
            elif message.startswith("DOWNLOAD_CLIENT:"):
                # Formato: "DOWNLOAD_CLIENT:protocol:filename"
                parts = message.split(":")
                logging.debug(f"Partes de mensaje DOWNLOAD_CLIENT: {parts}")
                protocol = parts[1]
                filename = parts[2]
                self.handle_download(addr, protocol, filename)
            else:
                logging.warning(f"Unknown client message from {addr}: {message}")
        except (ValueError, IndexError) as e:
            logging.warning(f"Invalid message format from {addr}: {data.decode()} - {e}")
