"""Formato de los mensajes que viajan por los sockets.

Cada mensaje es un objeto JSON en una sola línea, terminado en salto de
línea. Así el que recibe sabe dónde termina cada mensaje aunque lleguen
varios seguidos (como las notificaciones del observer).
"""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

ENCODING = "utf-8"


def _json_default(value: Any) -> Any:
    """Convierte los números Decimal de DynamoDB a int o float."""
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    raise TypeError(f"Tipo no serializable a JSON: {type(value).__name__}")


def encode(message: Any) -> bytes:
    """Convierte un mensaje en bytes listos para enviar por el socket."""
    text = json.dumps(message, default=_json_default, ensure_ascii=False)
    return (text + "\n").encode(ENCODING)


def decode(line: bytes | str) -> Any:
    """Convierte una línea recibida por el socket en un objeto de Python."""
    if isinstance(line, bytes):
        line = line.decode(ENCODING)
    return json.loads(line)
