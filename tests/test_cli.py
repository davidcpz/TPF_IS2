"""Tests de las utilidades de línea de comandos."""

from __future__ import annotations

import argparse
import logging

import pytest

from corporate_data_server.cli import (
    configure_logging,
    port_type,
    seconds_type,
    strip_equals,
    text_type,
)


def test_strip_equals() -> None:
    """Quita el '=' inicial que deja el formato -p=8080."""
    assert strip_equals("=8080") == "8080"
    assert strip_equals("8080") == "8080"


def test_text_type_valido() -> None:
    """Acepta un texto y le quita el '=' inicial."""
    assert text_type("=input.json") == "input.json"


@pytest.mark.parametrize("valor", ["", "=", "  "])
def test_text_type_vacio(valor: str) -> None:
    """Un texto vacío es un argumento malformado."""
    with pytest.raises(argparse.ArgumentTypeError):
        text_type(valor)


@pytest.mark.parametrize("valor", ["abc", "0", "65536", "-1"])
def test_port_type_invalido(valor: str) -> None:
    """Puertos no numéricos o fuera de rango se rechazan."""
    with pytest.raises(argparse.ArgumentTypeError):
        port_type(valor)


def test_seconds_type() -> None:
    """Acepta segundos positivos, con o sin decimales."""
    assert seconds_type("=30") == 30.0
    assert seconds_type("0.5") == 0.5


@pytest.mark.parametrize("valor", ["abc", "0", "-5"])
def test_seconds_type_invalido(valor: str) -> None:
    """Segundos no numéricos, cero o negativos se rechazan."""
    with pytest.raises(argparse.ArgumentTypeError):
        seconds_type(valor)


@pytest.mark.parametrize(
    ("verbose", "nivel"), [(True, logging.DEBUG), (False, logging.INFO)]
)
def test_configure_logging(verbose: bool, nivel: int) -> None:
    """Con -v nuestro código muestra DEBUG; sin -v, INFO."""
    configure_logging(verbose)
    assert (
        logging.getLogger("corporate_data_server.server").getEffectiveLevel() == nivel
    )


@pytest.mark.parametrize("verbose", [True, False])
def test_librerias_externas_solo_advertencias(verbose: bool) -> None:
    """Boto3 y botocore no llenan la pantalla, ni siquiera con -v."""
    configure_logging(verbose)
    for libreria in ("boto3", "botocore.credentials"):
        assert logging.getLogger(libreria).getEffectiveLevel() == logging.WARNING
