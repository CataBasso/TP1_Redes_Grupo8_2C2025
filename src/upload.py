import os
import sys
import time
from lib.upload_protocol import UploadProtocol
from lib.parser import get_parser

def main():
    args = get_parser("upload")

    if not args.host or not args.port or not args.src or not args.name:
        print("Usage: python3 upload.py -H <host> -p <port> -s <source> -n <name>")
        sys.exit(1)

    protocol = UploadProtocol(args)
    start_time = time.monotonic()
    upload = protocol.upload_file()
    end_time = time.monotonic()

    if upload:
        duration = end_time - start_time
        file_size_bytes = os.path.getsize(args.src)
        throughput_kbps = (file_size_bytes * 8) / (duration * 1024) if duration > 0 else 0
        
        print(f"\n--- Transferencia Completa ---")
        print(f"Tiempo total: {duration:.4f} segundos.")
        print(f"Velocidad promedio: {throughput_kbps:.2f} Kbps.")
    else:
        print("\nLa transferencia de archivos falló.")
        sys.exit(1)

if __name__ == "__main__":
    main()