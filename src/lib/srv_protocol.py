import os
import socket
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
        client_socket.settimeout(NetworkConfig.TIMEOUT)
        return client_socket, client_port

    def _negotiate_protocol(self, client_socket, addr):
        """Negocia el protocolo con el cliente"""
        protocol_data, _ = client_socket.recvfrom(NetworkConfig.BUFFER_SIZE)
        protocol = protocol_data.decode()
        client_socket.sendto(Messages.PROTOCOL_ACK, addr)
        return protocol

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

    def handle_upload(self, addr):
        """Maneja la subida de archivos desde un cliente."""
        print(f"Client {addr} connected for upload.")
        client_socket, client_port = self._setup_client_socket(addr)
        client_socket.sendto(Messages.UPLOAD_ACK, addr)
        client_socket.sendto(f"PORT:{client_port}".encode(), addr)

        try:
            protocol = self._negotiate_protocol(client_socket, addr)
            print(f"Client using protocol: {protocol}")

            # recibo nombre del archivo
            file_info, addr = client_socket.recvfrom(NetworkConfig.BUFFER_SIZE)
            filename, filesize = self._validate_file_info(file_info)
            print(f"Receiving file {filename} of size {filesize} bytes from {addr}")
            client_socket.sendto(Messages.FILE_INFO_ACK, addr)

            # constituyo la ruta del archivo
            storage_path = (
                self.args.storage if self.args.storage else FileInfo.DEFAULT_STORAGE
            )
            os.makedirs(storage_path, exist_ok=True)
            file_path = os.path.join(storage_path, filename)

            # Se decide el protocolo
            protocol_handler = self.get_protocol(protocol, self.args, client_socket)
            protocol_handler.receive_upload(client_socket, addr, filesize, file_path)

            # la linea que se comento anoche
            # client_socket.sendto(Messages.UPLOAD_COMPLETE, addr)
            print(f"File {filename} received successfully from {addr}")

        except socket.timeout:
            print(f"Timeout while receiving file from {addr}")
        except ValueError as e:
            print(f"Invalid data from {addr}: {e}")
            try:
                client_socket.sendto(Messages.ERROR_INVALID_FORMAT, addr)
            except:
                pass
        except socket.error as e:
            print(f"Socket error: {e}")
        except Exception as e:
            print(f"Unexpected error: {e}")
        finally:
            client_socket.close()

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
        finally:  # en ambos casos, cierro el socket temporal
            client_socket.close()

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
