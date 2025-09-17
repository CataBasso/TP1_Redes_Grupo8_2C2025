import socket
import os

BUFFER = 1024
TIMEOUT = 5

class StopAndWaitProtocol:
    def __init__(self, args, client_socket: socket.socket):
        self.args = args
        self.socket = client_socket
        self.socket.settimeout(TIMEOUT)

    def send_upload(self, file_size):
        with open(self.args.src, "rb") as file:
            seq_num = 0
            bytes_sent = 0
            while bytes_sent < file_size:
                chunk = file.read(BUFFER)
                bytes_read = len(chunk)

                packet = f"{seq_num}:".encode() + chunk

                ack_received = False
                retries = 0
                max_retries = 5

                while not ack_received and retries < max_retries:
                    self.socket.sendto(packet, (self.args.host, self.args.port))
                    
                    if self.args.verbose:
                        print(f"Sent packet {seq_num}, {bytes_read} bytes")

                    try:
                        data, addr = self.socket.recvfrom(BUFFER)
                        response = data.decode()
                        if response == f"ACK:{seq_num}":
                            ack_received = True
                            bytes_sent += bytes_read
                            seq_num = 1 - seq_num
                            
                        else:
                            print(f"Unexpected ACK: {response}, expected ACK:{seq_num}")
                    except socket.timeout:
                        retries += 1
                        print(f"Timeout waiting for ACK, retrying {retries}/{max_retries}")

                if retries >= max_retries:
                    print(f"Max retries reached for sequence number {seq_num}, upload failed.")
                    return False

            self.socket.sendto(b"EOF", (self.args.host, self.args.port))
            try:
                data, addr = self.socket.recvfrom(BUFFER)
                if data.decode() == "UPLOAD_COMPLETE":
                    print(f"File {self.args.name} uploaded successfully.")
                    return True
                else:
                    print(f"Unexpected response after EOF: {data.decode()}")
                    return False
            except socket.timeout:
                print("No response from server after sending EOF.")
                return False

    def receive_upload(
        self, client_socket: socket.socket, addr, filesize: int, file_path: str
    ):

        with open(file_path, "wb") as received_file:
            seq_expected = 0
            bytes_received = 0
            while bytes_received < filesize:
                packet, addr = client_socket.recvfrom(BUFFER)
                if packet == b"EOF":
                    break
                try:
                    seq_str, chunk = packet.split(b":", 1)
                    seq_received = int(seq_str)
                except Exception:
                    print(f"Packet format error from {addr}, ignoring.")
                    continue

                if seq_received == seq_expected:
                    received_file.write(chunk)
                    bytes_received += len(chunk)
                    client_socket.sendto(f"ACK:{seq_received}".encode(), addr)
                    seq_expected = 1 - seq_expected
                else:
                    client_socket.sendto(f"ACK:{1 - seq_expected}".encode(), addr)

            if bytes_received >= filesize:
                eof, addr = client_socket.recvfrom(BUFFER)
