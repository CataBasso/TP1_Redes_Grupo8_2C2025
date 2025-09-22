import socket

BUFFER_SIZE = 4096
TIMEOUT = 15  # seconds

class Socket:
    def __init__(self, host="0.0.0.0", port=0):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind((host, port))
        self.host = host
        self.port = port
        self.connectinos = {}
    
    def sendall():
        pass
    def recvall():
        pass
    
    def accept(self):
        if self.port == 0 and self.host=="0.0.0.0": 
            return
        #3 way handshake
        #listening

        while True:
            data, addr = self.socket.recvfrom(BUFFER_SIZE)
            if data.decode() == "UPLOAD_CLIENT": 
                client_socket = self._setup_client_socket()

                if not self.send_ack(client_socket, addr):
                    client_socket.close()
                    continue
                break
        return client_socket, addr
        
    def _setup_client_socket(self):
        """Configura el socket temporal del cliente"""
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        client_socket.bind(("", 0))
        # client_port = client_socket.getsockname()[1]
        client_socket.settimeout(TIMEOUT)
        return client_socket

    def send_ack(self, cliente_socket, addr):
        max_retries = 5
        retry_count = 0

        while retry_count < max_retries:
            try:
                cliente_socket.sendto(b"ACK", addr)
                print(f"Sent ACK to client {addr} (attempt {retry_count + 1})")

                data, addr_recv = cliente_socket.recvfrom(BUFFER_SIZE)
                if addr_recv == addr and data.decode() == "ACK":
                    print(f"Received ACK from client {addr}")
                    return True
                else:
                    print(
                        f"Received unexpected response from {addr_recv}: {data.decode()}"
                    )

            except cliente_socket.timeout:
                retry_count += 1
                print(
                    f"Timeout waiting for ACK from client {addr} (attempt {retry_count}/{max_retries})"
                )

        print(
            f"Failed to establish connection with client {addr} after {max_retries} attempts"
        )
        return False
    
    def close(self):
        self.socket.close()
        