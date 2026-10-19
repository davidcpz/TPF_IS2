"""Cliente ObserverClient: se suscribe y muestra cada actualización de datos.

Uso: python observerclient.py {-s=hostname} {-p=port} {-o=output.json} {-v}

Si la conexión se cae (o el servidor no está), reintenta cada 30 segundos
(configurable con -r) y, al reconectar, vuelve a enviar la suscripción.
"""

from __future__ import annotations

import argparse
import json
import logging
import socket
import threading
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Any

from corporate_data_server.cli import (
    configure_logging,
    port_type,
    seconds_type,
    text_type,
)
from corporate_data_server.protocol import decode, encode
from corporate_data_server.singleton_client import cpu_id

logger = logging.getLogger(__name__)

DEFAULT_HOST = "localhost"
DEFAULT_PORT = 8080
DEFAULT_RETRY_SECONDS = 30.0
CONNECT_TIMEOUT = 10.0
POLL_SECONDS = 0.5


class SubscriptionError(Exception):
    """El servidor rechazó la suscripción; reintentar no tiene sentido."""


class ObserverClient:
    """Mantiene la suscripción abierta y procesa cada notificación recibida."""

    def __init__(
        self,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        output: Path | None = None,
        retry_seconds: float = DEFAULT_RETRY_SECONDS,
        client_uuid: str | None = None,
    ) -> None:
        """Guarda la dirección del servidor y las opciones del cliente."""
        self.host = host
        self.port = port
        self.output = output
        self.retry_seconds = retry_seconds
        self.client_uuid = client_uuid or cpu_id()
        self.received = 0
        self._stop = threading.Event()

    def stop(self) -> None:
        """Pide que el cliente termine (se usa en los tests)."""
        self._stop.set()

    def run(self, max_connections: int | None = None) -> None:
        """Se conecta y escucha; si se corta, espera y vuelve a intentar."""
        attempts = 0
        while not self._stop.is_set():
            try:
                self._listen()
                logger.warning("El servidor cerró la conexión")
            except OSError as exc:
                logger.warning(
                    "Servidor %s:%d no disponible: %s", self.host, self.port, exc
                )
            attempts += 1
            if max_connections is not None and attempts >= max_connections:
                return
            logger.info("Reintentando en %g segundos...", self.retry_seconds)
            if self._stop.wait(self.retry_seconds):
                return

    def _listen(self) -> None:
        """Se suscribe y procesa notificaciones hasta que se corte la conexión."""
        address = (self.host, self.port)
        with socket.create_connection(address, timeout=CONNECT_TIMEOUT) as conn:
            conn.settimeout(POLL_SECONDS)
            conn.sendall(encode({"UUID": self.client_uuid, "ACTION": "subscribe"}))
            lines = self._read_lines(conn)
            ack_line = next(lines, None)
            if ack_line is None:
                return
            ack = decode(ack_line)
            if not isinstance(ack, dict) or ack.get("status") != "subscribed":
                raise SubscriptionError(f"Suscripción rechazada: {ack}")
            logger.info("Suscripto a %s:%d; esperando actualizaciones...", *address)
            for line in lines:
                try:
                    message = decode(line)
                except ValueError:
                    logger.warning("Mensaje inválido ignorado: %r", line)
                    continue
                self._handle(message)

    def _read_lines(self, conn: socket.socket) -> Iterator[bytes]:
        """Entrega las líneas recibidas; espera de a ratos cortos para no trabarse.

        Cada POLL_SECONDS la espera se interrumpe un instante: así Windows puede
        atender el Ctrl+C y el cliente puede ver si le pidieron parar.
        """
        buffer = b""
        while not self._stop.is_set():
            try:
                chunk = conn.recv(4096)
            except TimeoutError:
                continue  # no llegó nada todavía: volver a esperar
            if not chunk:
                return  # el servidor cerró la conexión
            buffer += chunk
            while b"\n" in buffer:
                line, buffer = buffer.split(b"\n", 1)
                yield line + b"\n"

    def _handle(self, message: Any) -> None:
        """Muestra la notificación y, si se pidió, la guarda en el archivo."""
        self.received += 1
        text = json.dumps(message, indent=2, ensure_ascii=False)
        print(text, flush=True)
        if self.output is not None:
            self.output.write_text(text + "\n", encoding="utf-8")
            logger.debug("Notificación guardada en %s", self.output)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Interpreta los argumentos: {-s=hostname} {-p=port} {-o=output.json} {-v}."""
    parser = argparse.ArgumentParser(
        prog="observerclient.py",
        description="Cliente suscripto a las actualizaciones de CorporateData.",
    )
    parser.add_argument("-s", "--server", type=text_type, default=DEFAULT_HOST)
    parser.add_argument("-p", "--port", type=port_type, default=DEFAULT_PORT)
    parser.add_argument("-o", "--output", type=text_type)
    parser.add_argument(
        "-r", "--retry", type=seconds_type, default=DEFAULT_RETRY_SECONDS
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Punto de entrada: corre hasta Ctrl+C; 1 si la suscripción es rechazada."""
    args = parse_args(argv)
    configure_logging(args.verbose)
    output = Path(args.output) if args.output else None
    client = ObserverClient(args.server, args.port, output, args.retry)
    try:
        client.run()
    except SubscriptionError as exc:
        logger.error("%s", exc)
        return 1
    except KeyboardInterrupt:
        logger.info("Cancelado por el usuario")
    return 0
