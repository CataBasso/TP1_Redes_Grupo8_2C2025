import socket
import os
from lib.selective_repeat_protocol import SelectiveRepeatProtocol
from lib.stop_and_wait_protocol import StopAndWaitProtocol
from lib.logger import get_logger

TIMEOUT = 2
BUFFER = 1024
MAX_RETRIES = 10

class DownloadProtocol:
    def __init__(self, args):
        self.args = args
        self.socket = None

    def download_file(self):
        logger = get_logger()
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        protocol = self.args.protocol if self.args.protocol else "stop-and-wait"
        
        handshake_msg = f"DOWNLOAD_CLIENT:{protocol}:{self.args.name}"
        logger.debug(f"Sending download request: {handshake_msg}")

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
                        logger.error(f"Invalid server response: {response}")
                        continue
                    try:
                        new_port = int(parts[1])
                        filesize = int(parts[2])
                    except ValueError:
                        logger.error(f"Invalid server response: {response}")
                        continue

                    if filesize <= 0:
                        logger.error(f"Invalid file size: {filesize}")
                        return False
                    
                    logger.info(f"Download accepted. Server assigned port {new_port}")
                    logger.debug(f"File size: {filesize} bytes, Protocol: {protocol}")
                    self.args.port = new_port
                    
                    if protocol == "stop-and-wait":
                        handler = StopAndWaitProtocol(self.args, self.socket)
                        return handler.receive_download(filesize)
                    elif protocol == "selective-repeat":
                        #handler = SelectiveRepeatProtocol(self.args, self.socket)
                        #return handler.receive_download(filesize)
                        pass
                elif response == "ERROR:FileNotFound":
                    logger.error("Requested file does not exist on server")
                    if self.socket:
                        self.socket.close()
                    return False
                else:
                    logger.error(f"Server rejected request: {response}")
                    return False

            except socket.timeout:
                retries += 1
                current_timeout *= 2
                logger.debug(f"Request timeout, retrying... ({retries}/{MAX_RETRIES})")
        
        logger.error("Could not establish connection with server")
        if self.socket:
            self.socket.close()
        return False