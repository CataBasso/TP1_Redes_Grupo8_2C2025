import sys
import time
import logging
from typing import Tuple

from lib.download_protocol import DownloadProtocol
from lib.parser import get_parser


SUCCESS = 0
ERROR = 1


def configure_logging(args) -> None:
    level = logging.INFO
    if getattr(args, "verbose", False):
        level = logging.DEBUG
    elif getattr(args, "quiet", False):
        level = logging.ERROR
    logging.basicConfig(level=level, format="%(asctime)s - %(levelname)s - %(message)s")


def validate_args(args) -> Tuple[bool, str]:
    if not args.host or not args.port or not args.dst or not args.name:
        return (
            False,
            "Usage: python3 download.py -H <host> -p <port> -d <destination> -n <name>",
        )
    try:
        port = int(args.port)
        if not (1 <= port <= 65535):
            return False, "Puerto inválido: debe estar entre 1 y 65535"
    except Exception:
        return False, "Puerto inválido: debe estar entre 1 y 65535"
    return True, ""


def main():
    args = get_parser("download")
    configure_logging(args)

    ok, msg = validate_args(args)
    if not ok:
        logging.error(msg)
        sys.exit(ERROR)

    try:
        protocol = DownloadProtocol(args)
        start_time = time.monotonic()
        success = protocol.download_file()
        end_time = time.monotonic()

        if success:
            protocol.close()
            duration = end_time - start_time
            logging.info("\n--- Transferencia Completa ---")
            logging.info(f"Tiempo total: {duration:.4f} segundos.")
            sys.exit(SUCCESS)
        else:
            logging.error("\nLa transferencia de archivos falló.")
            sys.exit(ERROR)

    except KeyboardInterrupt:
        logging.warning(
            "\nInterrupción recibida (Ctrl+C). Cancelando descarga de archivo..."
        )
        sys.exit(ERROR)
    except Exception as e:
        logging.exception(f"Error inesperado: {e}")
        sys.exit(ERROR)


if __name__ == "__main__":
    main()
