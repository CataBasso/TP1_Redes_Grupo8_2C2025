import numpy as np


class Package:
    def __init__(self, protocol='stop-and-wait'):
        self.protocol = protocol
        self.ACK = np.uint8(0)
        self.payload = np.array([], dtype=np.uint16)
        self.pyload_size =  np.uint32(0)
        

    def set_payload(self, payload):
        arr = [ord(ch) for ch in payload]
        self.payload = np.array(arr, dtype=np.uint16)
        self.payload_size = np.uint32(len(self.payload))


    def get_payload(self):
        return self.payload.tolist()
    
    def set_ACK(self, ACK):
        self.ACK = np.uint8(ACK)

    def get_ACK(self):
        return int(self.ACK)

    def get_payload_size(self):
        return int(self.pyload_size)
    
    def get_protocol(self):
        return self.protocol

    def __str__(self):
        decoded = ''.join(chr(x) for x in self.payload if x != 0)
        return (f"Package(protocol={self.protocol}\n"
                f" ACK={self.ACK}\n"
                f" payload_size={self.pyload_size}\n"
                f" payloadasdsads={decoded})")

    
    def encode(self):
        # Encode the package into bytes for transmission
        protocol_bytes = self.protocol.encode('utf-8')
        protocol_length = len(protocol_bytes)
        header = np.array([protocol_length], dtype=np.uint8).tobytes()
        ack_bytes = self.ACK.tobytes()
        payload_size_bytes = self.pyload_size.tobytes()
        payload_bytes = self.payload.tobytes()
        return header + protocol_bytes + ack_bytes + payload_size_bytes + payload_bytes
    
    def decode(self, data):
        # Decode bytes back into a package
        protocol_length = np.frombuffer(data[0:1], dtype=np.uint8)[0]
        protocol_end = 1 + protocol_length
        self.protocol = data[1:protocol_end].decode('utf-8')
        self.ACK = np.frombuffer(data[protocol_end:protocol_end+1], dtype=np.uint8)[0]
        self.pyload_size = np.frombuffer(data[protocol_end+1:protocol_end+5], dtype=np.uint32)[0]
        self.payload = np.frombuffer(data[protocol_end+5:protocol_end+5+self.pyload_size*2], dtype=np.uint16)
        return self