import socket
import sys
import argparse
import os

def argument_parser():
    parser = argparse.ArgumentParser(
        description="<command description>",
        usage="upload [-h] [-v | -q] [-H ADDR] [-p PORT] [-s FILEPATH] [-n FILENAME] [-r protocol]"
    )
    verbosity = parser.add_mutually_exclusive_group()
    verbosity.add_argument("-v", "--verbose", action="store_true", help="increase output verbosity")
    verbosity.add_argument("-q", "--quiet", action="store_true", help="decrease output verbosity")
    parser.add_argument("-H", "--host", metavar="", help="server IP address")
    parser.add_argument("-p", "--port", type=int, metavar="", help="server port")
    parser.add_argument("-s", "--src", metavar="", help="source file path")
    parser.add_argument("-n", "--name", metavar="", help="file name")
    parser.add_argument("-r", "--protocol", metavar="", help="error recovery protocol")

    parser._optionals.title = "optional arguments"
    return parser.parse_args()

def establish_connection(args):
    if not args.host or not args.port or not args.src or not args.name:
        print("Usage: python3 upload.py -H <host> -p <port> -s <source> -n <name>")
        sys.exit(1)

    upload_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    upload_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    upload_socket.settimeout(5)
    print(f"Connected to server at {args.host}:{args.port}")

    upload_socket.sendto(b"UPLOAD_CLIENT", (args.host, args.port))
    try:
        data, addr = upload_socket.recvfrom(1024)
        if data.decode() != "UPLOAD_ACK":
            print("Server did not acknowledge upload client.")
            sys.exit(1)
        
        new_port_data, uaddr = upload_socket.recvfrom(1024)
        if new_port_data.decode().startswith("PORT:"):
            new_port = int(new_port_data.decode().split(":")[1])
            print(f"Server assigned port {new_port} for file upload.")
            args.port = new_port
        else:
            print("Did not receive new port from server.")
            upload_socket.close()
            sys.exit(1)
    except socket.timeout:
        print("No response from server, exiting.")
        upload_socket.close()
        sys.exit(1)

    return upload_socket

def send_file_info(upload_socket, args):
    if not os.path.isfile(args.src):
        print(f"Source file {args.src} does not exist.")
        upload_socket.close()
        sys.exit(1)
    
    file_size = os.path.getsize(args.src)
    print(f"Uploading file {args.name} of size {file_size} bytes.")

    file_info = f"{args.name}:{file_size}"
    upload_socket.sendto(file_info.encode(), (args.host, args.port))
    
    try:
        data, addr = upload_socket.recvfrom(1024)
        if data.decode() != "FILE_INFO_ACK":
            print("Server did not acknowledge file info.")
            upload_socket.close()
            sys.exit(1)
    except socket.timeout:
        print("No response from server after sending file info, exiting.")
        upload_socket.close()
        sys.exit(1)
    
    return file_size

def send_stop_and_wait(args, upload_socket, file_size):
    with open(args.src, "rb") as file:
        seq_num = 0
        bytes_sent = 0
        while bytes_sent < file_size:
            chunk = file.read(1024)
            bytes_read = len(chunk)

            packet = f"{seq_num}:".encode() + chunk

            ack_received = False
            retries = 0
            max_retries = 5

            while not ack_received and retries < max_retries:
                upload_socket.sendto(packet, (args.host, args.port))
                
                # here, handle verbosity if needed  

                try:
                    data, addr = upload_socket.recvfrom(1024)
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
                upload_socket.close()
                sys.exit(1)

        upload_socket.sendto(b"EOF", (args.host, args.port))
        try:
            data, addr = upload_socket.recvfrom(1024)
            if data.decode() == "UPLOAD_COMPLETE":
                print(f"File {args.name} uploaded successfully.")
        except socket.timeout:
            print("No response from server after sending EOF.")

def send_file(upload_socket, args):
    protocol = args.protocol if args.protocol else "stop-and-wait"
    upload_socket.sendto(protocol.encode(), (args.host, args.port))
    
    try:
        data, saddr = upload_socket.recvfrom(1024)
        if data.decode() != "PROTOCOL_ACK":
            print("Server did not acknowledge protocol choice.")
            upload_socket.close()
            sys.exit(1)
    except socket.timeout:
        print("No response from server after sending protocol choice, exiting.")
        upload_socket.close()
        sys.exit(1)

    file_size = send_file_info(upload_socket, args)

    if protocol == "stop-and-wait":
        send_stop_and_wait(args, upload_socket, file_size)
    #elif args.protocol == "selective-repeat":
    #    selective_repeat(args, upload_socket, file_size)
    
def main():
    args = argument_parser()
    upload_socket = establish_connection(args)
    send_file(upload_socket, args)
    upload_socket.close()

if __name__ == "__main__":
    main()