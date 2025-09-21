import os
import socket
import time
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

    def _setup_client_socket(self, addr):
        """Configura el socket temporal del cliente"""
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        client_socket.bind(("", 0))
        client_port = client_socket.getsockname()[1]
        #client_socket.settimeout(NetworkConfig.TIMEOUT) si era esto me pongo a llorar
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

    # def handle_upload(self, addr):
    #     """Maneja la subida de archivos desde un cliente."""
    #     print(f"SERVIDOR: Hilo iniciado para atender upload de {addr}")
    #     client_socket, client_port = self._setup_client_socket(addr)

    #     print(f"SERVIDOR: Socket temporal creado en el puerto {client_port}")

    #     response = f"UPLOAD_ACK:{client_port}"
    #     print(f"SERVIDOR: Enviando respuesta combinada '{response}' a {addr}")
    #     client_socket.sendto(response.encode(), addr)

    #     try:
    #         protocol = self._negotiate_protocol(client_socket, addr)
    #         print(f"SERVIDOR: Cliente usa protocolo: {protocol}")

    #         protocol_handler = self.get_protocol(protocol, self.args, client_socket)

    #         # Esta función ahora manejará todo, desde recibir el file_info hasta el EOF.
    #         # Devuelve True/False y el nombre del archivo para el log.
    #         success, filename = protocol_handler.receive_upload(addr, self._validate_file_info)
           
    #         if success:
    #             print(f"File '{filename}' received successfully from {addr}")
    #         else:
    #             print(f"File transfer from {addr} failed.")
    #     except socket.timeout:
    #         print(f"Timeout en la conexión con {addr}. Cerrando hilo.")
    #     except Exception as e:
    #         print(f"Error inesperado en handle_upload: {e}")
    def handle_upload(self, addr, protocol, filename, filesize):
        try:
            client_socket, client_port = self._setup_client_socket(addr)
            print(f"SERVIDOR: Hilo para {addr} en puerto temporal {client_port}")

            # Enviamos la única confirmación con el nuevo puerto
            response = f"UPLOAD_OK:{client_port}"
            client_socket.sendto(response.encode(), addr)
            
            # Obtenemos el manejador de protocolo y procedemos directamente a recibir el archivo
            protocol_handler = self.get_protocol(protocol, self.args, client_socket)
            
            # Llamamos a la versión refactorizada de receive_upload
            success, _ = protocol_handler.receive_upload(addr, filename, filesize)

            if success:
                print(f"File '{filename}' received successfully from {addr}")
            else:
                print(f"File transfer from {addr} failed.")

        except Exception as e:
            print(f"Error fatal en el hilo de {addr}: {e}")

    def handle_download(self, addr):
        """Maneja la descarga de archivos hacia un cliente."""
        print(f"Client {addr} connected for download.")

        client_socket, client_port = self._setup_client_socket(addr)
        client_socket.sendto(Messages.DOWNLOAD_ACK, addr)
        client_socket.sendto(f"PORT:{client_port}".encode(), addr)

        try:
            protocol = self._negotiate_protocol(client_socket, addr)
            print(f"Client using protocol: {protocol}")

            # recibo nombre del archivo
            filename_data, _ = client_socket.recvfrom(NetworkConfig.BUFFER_SIZE)
            filename = filename_data.decode()

            # constituyo la ruta del archivo
            storage_path = (
                self.args.storage if self.args.storage else FileInfo.DEFAULT_STORAGE
            )
            file_path = os.path.join(storage_path, filename)

            # chequeo existencia, envío info al cliente y espero ack para enviar archivo
            if os.path.isfile(file_path):
                filesize = os.path.getsize(file_path)
                client_socket.sendto(f"FILESIZE:{filesize}".encode(), addr)
                ack_info, _ = client_socket.recvfrom(NetworkConfig.BUFFER_SIZE)
                if ack_info.decode() != Messages.FILE_INFO_ACK.decode():
                    return
            else:
                client_socket.sendto(Messages.ERROR_FILE_NOT_FOUND, addr)
                return

            # Se decide el protocolo
            protocol_handler = self.get_protocol(protocol, self.args, client_socket)
            success = protocol_handler.send_download(client_socket, addr, file_path)

            if success:
                print(f"File '{filename}' sent successfully to {addr}.")
            else:
                print(f"Failed to send file '{filename}' to {addr}.")

        except socket.timeout:  # si hay timeout
            print(f"Timeout during negotiation with client {addr}.")
        except ValueError as e:
            print(f"Protocol error with {addr}: {e}")
        except socket.error as e:
            print(f"Socket error: {e}")
        except Exception as e:
            print(f"Unexpected error: {e}")

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
        message = {
            ClientMessages.UPLOAD_CLIENT: self.handle_upload,
            ClientMessages.DOWNLOAD_CLIENT: self.handle_download,
        }
        func = message.get(data.decode())
        if func:
            func(addr)
        else:
            print(f"Unknown client message from {addr}: {data.decode()}")
