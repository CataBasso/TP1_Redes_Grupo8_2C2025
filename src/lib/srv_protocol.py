import os
import socket

TIMEOUT = 10
BUFFER = 1024
BUFFER_SR = 4096
BUFFER_SW = 4096


class ServerProtocol:
    def __init__(self, server_socket: socket.socket, args):
        self.server_socket = server_socket
        self.args = args

    def recieve_selective_repeat(
        self, client_socket: socket.socket, addr, filesize: int, file_path: str
    ) -> None:
        # lo que tengo que hacer basicamente es
        # recibir paquetes, ver si estan en orden,
        # si el paquete recibido está en orden, envio un ack
        # si el paquete recibido no está en orden, lo buffereo
        # cuando buffereo envio el ack del que recibi
        # en algun momento voy a volver a recibir el paquete perdido, una vez q lo recibi, saco todo del buffer
        # y envio el ack del paquete recibido
        seq_expected = 0
        bytes_received = 0
        buffer = []
        while bytes_received < filesize:
            packet, saddr = client_socket.recvfrom(BUFFER_SR)
            try:
                seq_str, chunk = packet.split(b":", 1)
                seq_received = int(seq_str)
            except Exception:
                print(f"Packet format error from {addr}, ignoring.")
                continue
            if seq_received == seq_expected:
                print("rec == expected")
                bytes_received += len(chunk)
                print(f"delivered: {seq_expected}")
                if len(buffer) > 0:
                    seq_expected += 1
                    # deliver pkts in buffer, basicamente me permite ir hasta el proximo paquete perdido
                    # te envio hasta el proximo paquete que se haya perdido
                    # voy aumentando el expected hasta llegar al elemento del buffer que no este en orden ahi dejo de hacer pop
                    for i in buffer:
                        if seq_expected == i[0]:
                            print(f"delivered: {seq_expected}")
                            seq_expected += 1  # se supone que en la primera posicion me quedo el ACK del último recibido válido
                        else:
                            print("have in buffer another packet loss")
                client_socket.sendto(f"ACK:{seq_received}".encode(), addr)
            else:
                print("rec != expected: queued")
                buffer.append((seq_received, chunk))
                client_socket.sendto(f"ACK:{seq_received}".encode(), addr)

    def recieve_stop_and_wait(
        self, client_socket: socket.socket, addr, filesize: int, file_path: str
    ) -> None:
        with open(file_path, "wb") as recieved_file:
            seq_expected = 0
            bytes_received = 0
            while bytes_received < filesize:
                packet, saddr = client_socket.recvfrom(BUFFER_SW)
                if packet == b"EOF":
                    break
                try:
                    seq_str, chunk = packet.split(b":", 1)
                    seq_received = int(seq_str)
                except Exception:
                    print(f"Packet format error from {addr}, ignoring.")
                    continue

                if seq_received == seq_expected:
                    recieved_file.write(chunk)
                    bytes_received += len(chunk)
                    client_socket.sendto(f"ACK:{seq_received}".encode(), addr)
                    seq_expected = 1 - seq_expected
                else:
                    client_socket.sendto(f"ACK:{1 - seq_expected}".encode(), addr)

            if bytes_received >= filesize:
                eof, saddr = client_socket.recvfrom(BUFFER)

    def handle_upload(self, addr) -> None:
        print(f"Client {addr} connected for upload.")

        client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        client_socket.bind(("", 0))
        client_port = client_socket.getsockname()[1]

        client_socket.sendto(b"UPLOAD_ACK", addr)
        client_socket.sendto(f"PORT:{client_port}".encode(), addr)
        client_socket.settimeout(TIMEOUT)

        try:
            protocol_data, _ = client_socket.recvfrom(BUFFER)
            protocol = protocol_data.decode()
            print(f"Client using protocol: {protocol}")
            client_socket.sendto(b"PROTOCOL_ACK", addr)

            file_info, saddr = client_socket.recvfrom(BUFFER)
            filename, filesize = file_info.decode().split(":")
            filesize = int(filesize)
            print(f"Receiving file {filename} of size {filesize} bytes from {addr}")
            client_socket.sendto(b"FILE_INFO_ACK", addr)

            storage_path = self.args.storage if self.args.storage else "storage"
            os.makedirs(storage_path, exist_ok=True)
            file_path = os.path.join(storage_path, filename)

            if protocol == "stop-and-wait":
                self.recieve_stop_and_wait(client_socket, addr, filesize, file_path)
            elif protocol == "selective-repeat":
                self.recieve_selective_repeat(client_socket, addr, filesize, file_path)

            client_socket.sendto(b"UPLOAD_COMPLETE", addr)
            print(f"File {filename} received successfully from {addr}")

        except socket.timeout:
            print(f"Timeout while receiving file from {addr}")
        finally:
            client_socket.close()

    def handle_download(self, addr) -> None:
        print(f"Client {addr} connected for download.")
        self.server_socket.sendto(b"DOWNLOAD_ACK", addr)
        # TODO: implement download logic
        return

    def handle_client(self, addr, data) -> None:
        message = data.decode()
        if message == "UPLOAD_CLIENT":
            self.handle_upload(addr)
        elif message == "DOWNLOAD_CLIENT":
            self.handle_download(addr)
        else:
            print(f"Unknown client message from {addr}: {message}")
