"""Cliente SingletonClient: envía un pedido al servidor y muestra la respuesta.

Uso: python singletonclient.py -i=input.json {-o=output.json} {-v}
"""

from __future__ import annotations

import argparse
import json
import logging
import socket
import uuid
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from corporate_data_server.cli import configure_logging, port_type, text_type
from corporate_data_server.protocol import decode, encode

logger = logging.getLogger(__name__)

DEFAULT_HOST = "localhost"
DEFAULT_PORT = 8080
TIMEOUT = 10.0


class ClientError(Exception):
    """Error del cliente: archivo de entrada inválido o servidor no disponible."""


def cpu_id() -> str:
    """Identificador único de la CPU, como en los ejemplos de la cátedra."""
    return str(uuid.getnode())


def load_request(path: Path) -> dict[str, Any]:
    """Lee el pedido del archivo JSON; si no trae UUID, usa el de esta CPU."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ClientError(f"No se pudo leer {path}: {exc}") from exc
    try:
        request = json.loads(text)
    except ValueError as exc:
        raise ClientError(f"{path} no contiene un JSON válido: {exc}") from exc
    if not isinstance(request, dict):
        raise ClientError(f"{path} debe contener un objeto JSON")
    if not str(request.get("UUID", "")).strip():
        request["UUID"] = cpu_id()
    return request


def send_request(
    request: dict[str, Any], host: str, port: int, timeout: float = TIMEOUT
) -> Any:
    """Envía el pedido al servidor y devuelve su respuesta."""
    try:
        with socket.create_connection((host, port), timeout=timeout) as conn:
            conn.sendall(encode(request))
            with conn.makefile("rb") as reader:
                line = reader.readline()
    except OSError as exc:
        raise ClientError(
            f"No se pudo comunicar con el servidor {host}:{port}: {exc}"
        ) from exc
    if not line:
        raise ClientError("El servidor cerró la conexión sin responder")
    try:
        return decode(line)
    except ValueError as exc:
        raise ClientError(f"Respuesta inválida del servidor: {exc}") from exc


def format_response(response: Any) -> str:
    """Da formato legible (con sangría) a la respuesta JSON."""
    return json.dumps(response, indent=2, ensure_ascii=False)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Interpreta los argumentos: -i=input.json {-o=output.json} {-v}."""
    parser = argparse.ArgumentParser(
        prog="singletonclient.py",
        description="Cliente que consulta o modifica CorporateData.",
    )
    parser.add_argument("-i", "--input", type=text_type, required=True)
    parser.add_argument("-o", "--output", type=text_type)
    parser.add_argument("-s", "--server", type=text_type, default=DEFAULT_HOST)
    parser.add_argument("-p", "--port", type=port_type, default=DEFAULT_PORT)
    parser.add_argument("-v", "--verbose", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Punto de entrada: 0 si la respuesta es correcta, 1 ante cualquier error."""
    args = parse_args(argv)
    configure_logging(args.verbose)
    try:
        request = load_request(Path(args.input))
        logger.debug("Pedido a %s:%d: %s", args.server, args.port, request)
        response = send_request(request, args.server, args.port)
    except ClientError as exc:
        logger.error("%s", exc)
        return 1
    text = format_response(response)
    if args.output:
        try:
            Path(args.output).write_text(text + "\n", encoding="utf-8")
        except OSError as exc:
            logger.error("No se pudo escribir %s: %s", args.output, exc)
            return 1
        logger.info("Respuesta guardada en %s", args.output)
    else:
        print(text)
    return 1 if isinstance(response, dict) and "Error" in response else 0
