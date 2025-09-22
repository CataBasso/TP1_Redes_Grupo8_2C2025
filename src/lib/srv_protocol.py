import os
import socket
from lib.stop_and_wait_protocol import StopAndWaitProtocol
from lib.selective_repeat_protocol import SelectiveRepeatProtocol
from lib.package import Package


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
    UPLOAD_CLIENT = 'u'
    DOWNLOAD_CLIENT = 'd'


# Protocol Names
class Protocols:
    STOP_AND_WAIT = "stop-and-wait"
    SELECTIVE_REPEAT = "selective-repeat"


# File Information
class FileInfo:
    SEPARATOR = ":"
    DEFAULT_STORAGE = "storage"


# =============================================================================
MAX_RETRIES = 10

class ServerProtocol:
    def __init__(self, args):
        self.args = args

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
                    protocol = msg
                    client_socket.sendto(Messages.PROTOCOL_ACK, addr)
                    return protocol
                else:
                    client_socket.sendto(Messages.PROTOCOL_ACK, addr)
            except socket.timeout:
                retries += 1
                print(f"Timeout waiting for protocol from {addr}, retrying {retries}/{max_retries}...")
        raise socket.timeout("Failed to negotiate protocol after several attempts.")

    def receive_file(self, client_socket,file_path,file_size):
        retries = 0
        while retries < MAX_RETRIES:
            data, addr = client_socket.recvfrom(1024)
            if "=" in data.decode():
                client_socket.sendto(b"FILE_INFO_ACK", addr)
                continue
            else:
                print(f"protocol type sw {repr(self.protocol_type)}, expected: {repr(Protocols.STOP_AND_WAIT)}")                
                if Protocols.STOP_AND_WAIT in self.protocol_type:
                    p = StopAndWaitProtocol(self.args,client_socket)
                    p.receive_upload(client_socket, addr, int(file_size), file_path)
                else:
                    pass


    def handle_upload(self, client_socket):
        """Maneja la subida de archivos desde un cliente."""
        print(f"Client connected for upload.")
        retries = 0
        while retries < MAX_RETRIES:
            data, addr = client_socket.recvfrom(1024)
            if "_" in data.decode():
                client_socket.sendto(b"PROTOCOL-ACK", addr)
                continue
            else:
                d = data.decode().split("=")
                filename = d[0]
                filesize = d[1]
                if filename is None or filesize is None:
                    print("Failed to receive valid file info.")
                    return
                # constituyo la ruta del archivo
                storage_path = (
                    self.args.storage if self.args.storage else FileInfo.DEFAULT_STORAGE
                )
                os.makedirs(storage_path, exist_ok=True)
                file_path = os.path.join(storage_path, filename)
                try:
                    print("sending FILE_INFO_ACK...") 
                    client_socket.sendto(b"FILE_INFO_ACK", addr)
                    break
                except socket.timeout:
                    retries += 1

        self.receive_file(client_socket, file_path, filesize)

        

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

    # def get_protocol(self, protocol_name, args, socket):
    #     """Devuelve el manejador de protocolo correspondiente."""
    #     protocols = {
    #         Protocols.STOP_AND_WAIT: StopAndWaitProtocol,
    #         Protocols.SELECTIVE_REPEAT: SelectiveRepeatProtocol,
    #     }
    #     if protocol_name in protocols:
    #         return protocols[protocol_name](args, socket)
    #     raise ValueError(f"Protocol {protocol_name} not supported")

    def handle_request(self, client_socket):
        retries = 0
        # message = {
        #     ClientMessages.UPLOAD_CLIENT: self.handle_upload,
        #     ClientMessages.DOWNLOAD_CLIENT: self.handle_download,
        # }

        while retries < 5:
            data, addr = client_socket.recvfrom(1024)
            p = Package()
            if '_' in data.decode(): 
                datas = data.decode().split('_')
                self.protocol_type = datas[0]
                client_type = datas[1]
                print(f"Client type: {repr(client_type)}")
                p.set_payload(data.decode())
                print("package object:", p.__str__())
            try:                
                client_socket.sendto(b"PROTOCOL-ACK", addr)
                print(f"Sent ACK to client {addr}")
                break                
                # hay que sacar el \n del client_type                          
            except socket.timeout:
                retries += 1
                print(f"Client didn't send protocol choice, retrying... {retries}")
        
        # hay que sacar el \n del client_type                             
        if "u" in client_type:
            print("entre a la u")
            self.handle_upload(client_socket)
        elif client_type == "d":
            self.handle_download(addr)



    