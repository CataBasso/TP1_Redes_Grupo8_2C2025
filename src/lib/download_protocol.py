import socket
import logging

from lib.selective_repeat_protocol import SelectiveRepeatProtocol
from lib.stop_and_wait_protocol import StopAndWaitProtocol

TIMEOUT = 2
BUFFER = 1024
MAX_RETRIES = 10


class DownloadProtocol:
    def __init__(self, args):
        self.args = args
        self.socket = None

    def download_file(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        protocol = self.args.protocol if self.args.protocol else "stop-and-wait"

        handshake_msg = f"DOWNLOAD_CLIENT:{protocol}:{self.args.name}"
        logging.info(f"CLIENTE: Enviando solicitud: {handshake_msg}")

        retries = 0
        current_timeout = TIMEOUT
        while retries < MAX_RETRIES:
            self.socket.sendto(handshake_msg.encode(), (self.args.host, self.args.port))
            try:
                self.socket.settimeout(current_timeout)
                data, _ = self.socket.recvfrom(BUFFER)
                response = data.decode()

                if response.startswith("DOWNLOAD_OK:"):
                    # Formato: "DOWNLOAD_OK:new_port:filesize"
                    parts = response.split(":")
                    if len(parts) != 3:
                        logging.error(
                            f"CLIENTE: Respuesta inválida del servidor: {response}"
                        )
                        continue
                    try:
                        new_port = int(parts[1])
                        filesize = int(parts[2])
                    except ValueError:
                        logging.error(
                            f"CLIENTE: Respuesta inválida del servidor: {response}"
                        )
                        continue

                    if filesize <= 0:
                        logging.error(
                            f"CLIENTE: Tamaño de archivo inválido: {filesize}"
                        )
                        return False

                    logging.info(
                        f"CLIENTE: Descarga aceptada. Puerto {new_port}, archivo {filesize} bytes."
                    )
                    self.args.port = new_port

                    if protocol == "stop-and-wait":
                        handler = StopAndWaitProtocol(self.args, self.socket)
                        return handler.receive_download(filesize)
                    elif protocol == "selective-repeat":
                        handler = SelectiveRepeatProtocol(self.args, self.socket)
                        return handler.receive_download(filesize)
                elif response == "ERROR:FileNotFound":
                    logging.error(
                        "CLIENTE: El archivo solicitado no existe en el servidor."
                    )
                    if self.socket:
                        self.socket.close()
                    return False
                else:
                    logging.error(
                        f"CLIENTE: El servidor rechazó la solicitud: {response}"
                    )
                    return False

            except socket.timeout:
                retries += 1
                current_timeout *= 2
                logging.warning(
                    f"CLIENTE: Timeout en solicitud, reintentando... ({retries}/{MAX_RETRIES})"
                )

        logging.error("CLIENTE: No se pudo establecer conexión con el servidor.")
        if self.socket:
            self.socket.close()
        return False

    def close(self):
        if self.socket:
            self.socket.close()
        self.socket = None
        logging.info("CLIENTE: Socket cerrado.")
