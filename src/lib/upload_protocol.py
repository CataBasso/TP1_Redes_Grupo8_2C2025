import socket
import os
from lib.selective_repeat_protocol import SelectiveRepeatProtocol
from lib.stop_and_wait_protocol import StopAndWaitProtocol

TIMEOUT = 5
BUFFER = 1024
MAX_RETRIES = 5

class UploadProtocol:
    def __init__(self, args):
        self.args = args
        self.socket = None

    def establish_connection(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.settimeout(TIMEOUT)
        print(f"Connecting to server at {self.args.host}:{self.args.port}")

        retries = 0
        while retries < MAX_RETRIES:
            self.socket.sendto(b"UPLOAD_CLIENT", (self.args.host, self.args.port))
            try:
                data, addr = self.socket.recvfrom(BUFFER)
                if data.decode() != "UPLOAD_ACK":
                    print("Server did not acknowledge upload client.")
                    return False

                new_port_data, addr = self.socket.recvfrom(BUFFER)
                if new_port_data.decode().startswith("PORT:"):
                    new_port = int(new_port_data.decode().split(":")[1])
                    print(f"Server assigned port {new_port} for file upload.")
                    self.args.port = new_port
                    return True
                else:
                    print("Did not receive new port from server.")
                    return False
            except socket.timeout:
                retries += 1
                print(f"No response from server, retrying... {retries}/{MAX_RETRIES}")

        print("Max retries reached, exiting.")
        return False
    
    def send_protocol_info(self):
        protocol = self.args.protocol if self.args.protocol else "stop-and-wait"
        retries = 0
        
        while retries < MAX_RETRIES:
            self.socket.sendto(protocol.encode(), (self.args.host, self.args.port))

            try:
                data, addr = self.socket.recvfrom(BUFFER)
                if data.decode() != "PROTOCOL_ACK":
                    print("Server did not acknowledge protocol choice.")
                    return False
                return True
            except socket.timeout:
                retries += 1
                print(f"No response from server after sending protocol choice, retrying... {retries}/{MAX_RETRIES}")
                
        print("Max retries reached, exiting.")
        return False

    def send_file_info(self):
        retries = 0
        if not os.path.isfile(self.args.src):
            print(f"Source file {self.args.src} does not exist.")
            return None

        file_size = os.path.getsize(self.args.src)
        print(f"Uploading file {self.args.name} of size {file_size} bytes.")

        file_info = f"{self.args.name}:{file_size}"
        while retries < MAX_RETRIES:
            self.socket.sendto(file_info.encode(), (self.args.host, self.args.port))

            try:
                data, addr = self.socket.recvfrom(BUFFER)
                if data.decode() != "FILE_INFO_ACK":
                    print("Server did not acknowledge file info.")
                    return None
                return file_size
            except socket.timeout:
                retries += 1
                print(f"No response from server after sending file info, retrying... {retries}/{MAX_RETRIES}")

        print("Max retries reached, exiting.")    
        return False

    def upload_file(self):
        if not self.establish_connection():
            return False

        if not self.send_protocol_info():
            return False

        file_size = self.send_file_info()
        if file_size is None:
            return False

        protocol = self.args.protocol if self.args.protocol else "stop-and-wait"
        if protocol == "stop-and-wait":
            stop_and_wait = StopAndWaitProtocol(self.args, self.socket)
            return stop_and_wait.send_upload(file_size)
        elif protocol == "selective-repeat":
            selective_repeat = SelectiveRepeatProtocol(self.args, self.socket)
            return selective_repeat.send_upload(file_size)
