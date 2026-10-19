"""Tests del cliente SingletonClient contra un servidor real con tablas simuladas."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from conftest import REGISTRO_INICIAL, ServidorDePrueba, puerto_libre
from corporate_data_server.singleton_client import (
    ClientError,
    cpu_id,
    load_request,
    main,
    parse_args,
    send_request,
)


def escribir(tmp_path: Path, contenido: object, nombre: str = "input.json") -> Path:
    """Escribe un archivo JSON de entrada y devuelve su ruta."""
    ruta = tmp_path / nombre
    ruta.write_text(json.dumps(contenido), encoding="utf-8")
    return ruta


# ---------- Lectura del archivo de entrada ----------


def test_load_request_completa_el_uuid(tmp_path: Path) -> None:
    """Si el archivo no trae UUID, se usa el identificador de esta CPU."""
    pedido = load_request(escribir(tmp_path, {"ACTION": "list"}))
    assert pedido["UUID"] == cpu_id()


def test_load_request_respeta_el_uuid(tmp_path: Path) -> None:
    """Si el archivo trae UUID, se respeta."""
    pedido = load_request(escribir(tmp_path, {"UUID": "CPU-9", "ACTION": "list"}))
    assert pedido["UUID"] == "CPU-9"


def test_load_request_archivo_inexistente(tmp_path: Path) -> None:
    """Un archivo que no existe produce ClientError."""
    with pytest.raises(ClientError, match="No se pudo leer"):
        load_request(tmp_path / "no_existe.json")


def test_load_request_json_invalido(tmp_path: Path) -> None:
    """Un archivo que no es JSON produce ClientError."""
    ruta = tmp_path / "input.json"
    ruta.write_text("{esto no es json", encoding="utf-8")
    with pytest.raises(ClientError, match="JSON válido"):
        load_request(ruta)


def test_load_request_debe_ser_objeto(tmp_path: Path) -> None:
    """Un JSON que no es un objeto (por ejemplo, una lista) se rechaza."""
    with pytest.raises(ClientError, match="objeto JSON"):
        load_request(escribir(tmp_path, [1, 2, 3]))


# ---------- Comunicación con el servidor ----------


def test_send_request_get(servidor: ServidorDePrueba) -> None:
    """Un get llega al servidor y vuelve el registro."""
    respuesta = send_request(
        {"UUID": "CPU-1", "ACTION": "get", "ID": REGISTRO_INICIAL["id"]},
        "127.0.0.1",
        servidor.port,
    )
    assert respuesta == REGISTRO_INICIAL


def test_servidor_caido_produce_client_error() -> None:
    """Con el servidor caído, el cliente informa un error claro."""
    with pytest.raises(ClientError, match="No se pudo comunicar"):
        send_request({"UUID": "X", "ACTION": "list"}, "127.0.0.1", puerto_libre(), 2)


# ---------- Programa completo ----------


def test_main_list_muestra_la_respuesta(
    servidor: ServidorDePrueba, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Main con list imprime el array de registros y devuelve 0."""
    entrada = escribir(tmp_path, {"ACTION": "list"})
    codigo = main(["-i", str(entrada), "-p", str(servidor.port), "-s", "127.0.0.1"])
    assert codigo == 0
    salida = capsys.readouterr().out
    assert json.loads(salida[salida.index("[") :]) == [REGISTRO_INICIAL]
    assert list(servidor.log.items.values())[0]["action"] == "list"


def test_main_set_guarda_en_archivo_de_salida(
    servidor: ServidorDePrueba, tmp_path: Path
) -> None:
    """Main con set y -o guarda la respuesta en el archivo indicado."""
    entrada = escribir(
        tmp_path, {"ACTION": "set", "ID": REGISTRO_INICIAL["id"], "cp": "3100"}
    )
    salida = tmp_path / "output.json"
    codigo = main(
        [f"-i={entrada}", f"-o={salida}", f"-p={servidor.port}", "-s=127.0.0.1"]
    )
    assert codigo == 0
    assert json.loads(salida.read_text(encoding="utf-8"))["cp"] == "3100"
    assert servidor.data.items[REGISTRO_INICIAL["id"]]["cp"] == "3100"


def test_main_respuesta_de_error_devuelve_1(
    servidor: ServidorDePrueba, tmp_path: Path
) -> None:
    """Un pedido sin datos mínimos recibe Error y main devuelve 1."""
    entrada = escribir(tmp_path, {"ACTION": "get"})
    assert main(["-i", str(entrada), "-p", str(servidor.port), "-s", "127.0.0.1"]) == 1


def test_main_servidor_caido_devuelve_1(tmp_path: Path) -> None:
    """Con el servidor caído, main informa el error y devuelve 1."""
    entrada = escribir(tmp_path, {"ACTION": "list"})
    assert main(["-i", str(entrada), "-p", str(puerto_libre()), "-s", "127.0.0.1"]) == 1


def test_main_archivo_inexistente_devuelve_1(tmp_path: Path) -> None:
    """Un archivo de entrada inexistente termina con código 1."""
    assert main(["-i", str(tmp_path / "no_existe.json")]) == 1


def test_main_no_puede_escribir_la_salida(
    servidor: ServidorDePrueba, tmp_path: Path
) -> None:
    """Si no se puede escribir el archivo de salida, devuelve 1."""
    entrada = escribir(tmp_path, {"ACTION": "list"})
    salida = tmp_path / "carpeta_inexistente" / "output.json"
    codigo = main(
        [
            "-i",
            str(entrada),
            "-o",
            str(salida),
            "-p",
            str(servidor.port),
            "-s",
            "127.0.0.1",
        ]
    )
    assert codigo == 1


@pytest.mark.parametrize("argv", [[], ["-i"], ["-i=x.json", "-p=abc"], ["-x"]])
def test_argumentos_malformados(argv: list[str]) -> None:
    """Argumentos inválidos o faltantes terminan con código 2."""
    with pytest.raises(SystemExit) as salida:
        parse_args(argv)
    assert salida.value.code == 2
