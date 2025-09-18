import socket

from lib.selective_repeat_protocol import SelectiveRepeatProtocol
from lib.stop_and_wait_protocol import StopAndWaitProtocol

BUFFER = 1024
TIMEOUT = 5

class DownloadProtocol:
    def __init__(self, args):
        self.args = args
        self.socket = None

    def establish_connection(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.settimeout(TIMEOUT)
        print(f"Contacting server at {self.args.host}:{self.args.port}")
        self.socket.sendto(b"DOWNLOAD_CLIENT", (self.args.host, self.args.port))
        try:
            data, _ = self.socket.recvfrom(BUFFER)
            if data.decode() != "DOWNLOAD_ACK":
                print("Server did not acknowledge download request.")
                return False
            port_data, _ = self.socket.recvfrom(BUFFER)
            if port_data.decode().startswith("PORT:"):
                new_port = int(port_data.decode().split(":")[1])
                print(f"Server assigned new port {new_port} for the download.")
                self.args.port = new_port
            else:
                print("Did not receive a valid new port from server.")
                return False
        except socket.timeout:
            print("No response from server. Exiting.")
            return False
        return True

    def send_protocol_info(self):
        protocol = self.args.protocol if self.args.protocol else "stop-and-wait"
        self.socket.sendto(protocol.encode(), (self.args.host, self.args.port))
        try:
            ack_data, _ = self.socket.recvfrom(BUFFER)
            if ack_data.decode() != "PROTOCOL_ACK":
                print("Server did not acknowledge protocol choice.")
                return False
        except socket.timeout:
            print("No response from server after sending protocol choice. Exiting.")
            return False
        return True

    def request_file_info(self):
        print(f"Requesting file '{self.args.name}' from server.")
        self.socket.sendto(self.args.name.encode(), (self.args.host, self.args.port))
        try:
            file_info, _ = self.socket.recvfrom(BUFFER)
            info_str = file_info.decode()
            if info_str.startswith("FILESIZE:"):
                filesize = int(info_str.split(":")[1])
                print(f"Server confirmed file exists. Size: {filesize} bytes.")
                self.socket.sendto(b"FILE_INFO_ACK", (self.args.host, self.args.port))
                return filesize
            elif info_str == "ERROR:FileNotFound":
                print("Server responded: File not found.")
                return None
            else:
                print(f"Unexpected response from server: {info_str}")
                return None
        except socket.timeout:
            print("No response from server after requesting file info, exiting.")
            return None

    def download_file(self):
        if not self.establish_connection():
            return False
        if not self.send_protocol_info():
            return False
        filesize = self.request_file_info()
        if not filesize:
            return False
        protocol = self.args.protocol if self.args.protocol else "stop-and-wait"
        if protocol == "stop-and-wait":
            stop_and_wait = StopAndWaitProtocol(self.args, self.socket)
            return stop_and_wait.receive_download()
        elif protocol == "selective-repeat":
            selective_repeat = SelectiveRepeatProtocol(self.args, self.socket)
            return selective_repeat.recieve_download(filesize)
        return False