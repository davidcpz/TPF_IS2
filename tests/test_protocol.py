"""Tests del formato de mensajes."""

from __future__ import annotations

from decimal import Decimal

import pytest

from corporate_data_server.protocol import decode, encode


def test_encode_termina_en_salto_de_linea() -> None:
    """Cada mensaje es una sola línea terminada en salto de línea."""
    datos = encode({"ACTION": "list"})
    assert datos.endswith(b"\n")
    assert datos.count(b"\n") == 1


def test_ida_y_vuelta() -> None:
    """Codificar y decodificar devuelve el mismo mensaje."""
    mensaje = {"UUID": "123", "ACTION": "get", "ID": "UADER-FCyT-IS2"}
    assert decode(encode(mensaje)) == mensaje


def test_conserva_acentos() -> None:
    """Los acentos viajan sin problemas."""
    mensaje = {"localidad": "Concepción del Uruguay"}
    assert decode(encode(mensaje)) == mensaje


def test_decimal_entero_se_convierte_en_int() -> None:
    """Un Decimal sin parte decimal (como los de DynamoDB) pasa a int."""
    assert decode(encode({"idreq": Decimal("473")})) == {"idreq": 473}


def test_decimal_con_decimales_se_convierte_en_float() -> None:
    """Un Decimal con parte decimal pasa a float."""
    assert decode(encode({"valor": Decimal("1.5")})) == {"valor": 1.5}


def test_decode_acepta_texto() -> None:
    """Decode también acepta un str además de bytes."""
    assert decode('{"a": 1}') == {"a": 1}


def test_tipo_no_serializable_da_error() -> None:
    """Un objeto que no es JSON produce TypeError."""
    with pytest.raises(TypeError):
        encode({"x": object()})
