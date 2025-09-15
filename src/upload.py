import socket
import sys

if len(sys.argv) != 3:
    print("Usage: python3 upload.py <host> <port>")
    sys.exit(1)

host = sys.argv[1]
port = int(sys.argv[2])

client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
client_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
client_socket.connect((host, port))
print(f"Connected to server at {host}:{port}")

while True:
    message = input("Enter message to send (or 'exit' to quit): ")
    client_socket.sendto(message.encode(), (host, port))

    if message == "exit":
        print("Exiting client.")
        break

    data, addr = client_socket.recvfrom(1024)
    print(f"Received from server: {data.decode()}")

client_socket.close()