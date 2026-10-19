"""Utilidades compartidas por los tres programas de línea de comandos."""

from __future__ import annotations

import argparse
import logging
import sys

APP_LOGGER = "corporate_data_server"
NOISY_LIBRARIES = ("boto3", "botocore", "urllib3")


def strip_equals(value: str) -> str:
    """Permite escribir los argumentos como -p=8080 además de -p 8080."""
    return value[1:] if value.startswith("=") else value


def text_type(value: str) -> str:
    """Valida un argumento de texto (nombre de archivo o de servidor)."""
    text = strip_equals(value).strip()
    if not text:
        raise argparse.ArgumentTypeError("el valor no puede estar vacío")
    return text


def port_type(value: str) -> int:
    """Valida que el puerto sea un número entre 1 y 65535."""
    try:
        port = int(strip_equals(value))
    except ValueError:
        raise argparse.ArgumentTypeError(f"puerto inválido: {value!r}") from None
    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError(f"puerto fuera de rango: {port}")
    return port


def seconds_type(value: str) -> float:
    """Valida una cantidad de segundos mayor que cero."""
    try:
        seconds = float(strip_equals(value))
    except ValueError:
        raise argparse.ArgumentTypeError(f"segundos inválidos: {value!r}") from None
    if seconds <= 0:
        raise argparse.ArgumentTypeError("los segundos deben ser mayores que cero")
    return seconds


def configure_logging(verbose: bool) -> None:
    """Muestra los mensajes por salida estándar; con -v incluye los de debug.

    El modo detallado se aplica solo a nuestro código: las librerías externas
    (boto3, botocore) muestran únicamente advertencias y errores.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stdout,
        force=True,
    )
    logging.getLogger(APP_LOGGER).setLevel(logging.DEBUG if verbose else logging.INFO)
    for library in NOISY_LIBRARIES:
        logging.getLogger(library).setLevel(logging.WARNING)
