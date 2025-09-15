import socket
import sys

if len (sys.argv) != 3:
    print("Usage: python3 start-server.py <host> <port>")
    sys.exit(1)

host = sys.argv[1]
port = int(sys.argv[2])

server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server_socket.bind((host, port))
print(f"Server listening on {host}:{port}")

while True:
    data, addr = server_socket.recvfrom(1024)
    server_socket.connect(addr)

    if not data or data.decode() == "exit":
        print("Exiting server.")
        break
    
    print(f"Received message: {data.decode()} from {addr}")
    server_socket.sendto(b"ACK", addr)

server_socket.close()