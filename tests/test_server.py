"""Tests del servidor TCP, usando sockets reales y tablas simuladas."""

from __future__ import annotations

import socket
import threading
import time
from collections.abc import Iterator
from typing import Any

import pytest

from corporate_data_server import server as server_module
from corporate_data_server.observer import Subject
from corporate_data_server.protocol import decode, encode
from corporate_data_server.proxy import CorporateDataProxy
from corporate_data_server.server import (
    DEFAULT_PORT,
    CorporateServer,
    ServerError,
    main,
    parse_args,
)
from corporate_data_server.tables import CorporateDataTable, CorporateLogTable
from fakes import FakeTable

REGISTRO = {"id": "UADER-FCyT-IS2", "sede": "FCyT"}


class Entorno:
    """Servidor real en un puerto libre, con tablas en memoria."""

    def __init__(self) -> None:
        """Arma las tablas, el proxy y el servidor (sin arrancarlo)."""
        self.data = FakeTable()
        self.log = FakeTable()
        self.data.items[REGISTRO["id"]] = dict(REGISTRO)
        self.sujeto = Subject()
        proxy = CorporateDataProxy(
            CorporateDataTable(self.data), CorporateLogTable(self.log), self.sujeto
        )
        self.server = CorporateServer(proxy, self.sujeto, host="127.0.0.1", port=0)

    def enviar(self, mensaje: bytes) -> Any:
        """Abre una conexión, envía el mensaje y devuelve la respuesta."""
        with socket.create_connection(("127.0.0.1", self.server.port), 5) as conn:
            conn.sendall(mensaje)
            return decode(conn.makefile("rb").readline())

    def pedir(self, **pedido: Any) -> Any:
        """Envía un pedido JSON como lo haría singletonclient."""
        return self.enviar(encode({"UUID": "CPU-1", **pedido}))


def esperar(condicion: Any, segundos: float = 3.0) -> bool:
    """Espera a que la condición se cumpla, como máximo unos segundos."""
    limite = time.monotonic() + segundos
    while time.monotonic() < limite:
        if condicion():
            return True
        time.sleep(0.02)
    return False


@pytest.fixture
def entorno() -> Iterator[Entorno]:
    """Levanta el servidor en un hilo y lo detiene al terminar el test."""
    CorporateDataTable.reset_instance()
    CorporateLogTable.reset_instance()
    env = Entorno()
    env.server.start()
    hilo = threading.Thread(target=env.server.serve_forever, daemon=True)
    hilo.start()
    yield env
    env.server.shutdown()
    hilo.join(timeout=5)
    CorporateDataTable.reset_instance()
    CorporateLogTable.reset_instance()


# ---------- Pedidos por socket ----------


def test_get_por_socket(entorno: Entorno) -> None:
    """Un get enviado por TCP devuelve el registro."""
    assert entorno.pedir(ACTION="get", ID=REGISTRO["id"]) == REGISTRO


def test_list_por_socket(entorno: Entorno) -> None:
    """Un list enviado por TCP devuelve un array."""
    assert entorno.pedir(ACTION="list") == [REGISTRO]


def test_set_por_socket_queda_guardado(entorno: Entorno) -> None:
    """Un set enviado por TCP modifica la tabla."""
    respuesta = entorno.pedir(ACTION="set", ID=REGISTRO["id"], cp="3260")
    assert respuesta["cp"] == "3260"
    assert entorno.data.items[REGISTRO["id"]]["cp"] == "3260"


def test_cada_conexion_tiene_su_propia_sesion(entorno: Entorno) -> None:
    """Dos pedidos en conexiones distintas quedan con sesiones distintas."""
    entorno.pedir(ACTION="list")
    entorno.pedir(ACTION="list")
    sesiones = {log["sessionid"] for log in entorno.log.items.values()}
    assert len(sesiones) == 2


def test_json_invalido_devuelve_error(entorno: Entorno) -> None:
    """Un mensaje que no es JSON recibe un Error y no se registra."""
    respuesta = entorno.enviar(b"esto no es json\n")
    assert "JSON" in respuesta["Error"]
    assert entorno.log.items == {}


def test_pedido_sin_datos_minimos(entorno: Entorno) -> None:
    """Un get sin ID recibe un Error."""
    assert "ID" in entorno.pedir(ACTION="get")["Error"]


def test_conexion_vacia_no_rompe_el_servidor(entorno: Entorno) -> None:
    """Un cliente que se conecta y corta sin enviar nada no afecta al servidor."""
    socket.create_connection(("127.0.0.1", entorno.server.port), 5).close()
    assert entorno.pedir(ACTION="list") == [REGISTRO]


# ---------- Suscripción (Observer) ----------


def test_suscriptor_recibe_las_notificaciones(entorno: Entorno) -> None:
    """Un suscriptor queda conectado y recibe cada set."""
    with socket.create_connection(("127.0.0.1", entorno.server.port), 5) as sub:
        sub.sendall(encode({"UUID": "CPU-OBS", "ACTION": "subscribe"}))
        lector = sub.makefile("rb")
        assert decode(lector.readline())["status"] == "subscribed"
        assert esperar(lambda: entorno.sujeto.count == 1)

        entorno.pedir(ACTION="set", ID=REGISTRO["id"], telefono="111")
        assert decode(lector.readline())["telefono"] == "111"

        entorno.pedir(ACTION="set", ID=REGISTRO["id"], telefono="222")
        assert decode(lector.readline())["telefono"] == "222"


def test_suscriptor_que_corta_se_quita(entorno: Entorno) -> None:
    """Cuando el suscriptor cierra la conexión, sale de la lista."""
    sub = socket.create_connection(("127.0.0.1", entorno.server.port), 5)
    sub.sendall(encode({"UUID": "CPU-OBS", "ACTION": "subscribe"}))
    sub.makefile("rb").readline()
    assert esperar(lambda: entorno.sujeto.count == 1)
    sub.close()
    assert esperar(lambda: entorno.sujeto.count == 0)


def test_suscripcion_invalida_se_cierra(entorno: Entorno) -> None:
    """Un subscribe sin UUID recibe Error y no queda registrado."""
    respuesta = entorno.enviar(encode({"ACTION": "subscribe"}))
    assert "UUID" in respuesta["Error"]
    assert entorno.sujeto.count == 0


def test_shutdown_cierra_a_los_suscriptores(entorno: Entorno) -> None:
    """Al detener el servidor, los suscriptores ven el fin de la conexión."""
    sub = socket.create_connection(("127.0.0.1", entorno.server.port), 5)
    sub.sendall(encode({"UUID": "CPU-OBS", "ACTION": "subscribe"}))
    lector = sub.makefile("rb")
    lector.readline()
    assert esperar(lambda: entorno.sujeto.count == 1)
    entorno.server.shutdown()
    try:
        fin = lector.readline()
    except ConnectionError:
        fin = b""  # en Windows el corte puede llegar como "reset"
    assert fin == b""
    sub.close()


# ---------- Arranque ----------


def test_no_se_puede_levantar_dos_veces_en_el_mismo_puerto(
    entorno: Entorno,
) -> None:
    """Un segundo servidor en el mismo puerto falla con ServerError."""
    segundo = CorporateServer(
        CorporateDataProxy(CorporateDataTable(), CorporateLogTable(), Subject()),
        Subject(),
        host="127.0.0.1",
        port=entorno.server.port,
    )
    with pytest.raises(ServerError):
        segundo.start()


def test_puerto_por_defecto() -> None:
    """Sin argumentos, el puerto es 8080 y sin modo detallado."""
    args = parse_args([])
    assert args.port == DEFAULT_PORT
    assert args.verbose is False


@pytest.mark.parametrize("argv", [["-p=9000"], ["-p", "9000"], ["--port=9000"]])
def test_formatos_del_argumento_puerto(argv: list[str]) -> None:
    """El puerto se acepta como -p=9000, -p 9000 o --port=9000."""
    assert parse_args(argv).port == 9000


@pytest.mark.parametrize("argv", [["-p=abc"], ["-p=0"], ["-p=70000"], ["-x"]])
def test_argumentos_malformados_terminan_con_error(argv: list[str]) -> None:
    """Argumentos inválidos terminan el programa con código 2."""
    with pytest.raises(SystemExit) as salida:
        parse_args(argv)
    assert salida.value.code == 2


def test_main_detecta_puerto_ocupado(
    entorno: Entorno, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Main devuelve 1 si ya hay un servidor en ese puerto."""
    ocupado = CorporateServer(
        CorporateDataProxy(CorporateDataTable(), CorporateLogTable(), Subject()),
        Subject(),
        host="127.0.0.1",
        port=entorno.server.port,
    )
    monkeypatch.setattr(server_module, "build_server", lambda port: ocupado)
    assert main(["-p", str(entorno.server.port)]) == 1


def test_main_se_detiene_con_ctrl_c(monkeypatch: pytest.MonkeyPatch) -> None:
    """Main termina con código 0 cuando se cancela con Ctrl+C."""
    CorporateDataTable.reset_instance()
    CorporateLogTable.reset_instance()
    env = Entorno()

    def cancelar() -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(env.server, "serve_forever", cancelar)
    monkeypatch.setattr(server_module, "build_server", lambda port: env.server)
    assert main(["-p", "9999", "-v"]) == 0
    CorporateDataTable.reset_instance()
    CorporateLogTable.reset_instance()


def test_build_server_usa_las_tablas_reales(monkeypatch: pytest.MonkeyPatch) -> None:
    """build_server arma el servidor conectando las dos tablas Singleton."""
    CorporateDataTable.reset_instance()
    CorporateLogTable.reset_instance()
    monkeypatch.setattr(
        "corporate_data_server.tables.connect_table", lambda name: FakeTable()
    )
    servidor = server_module.build_server(9999)
    assert servidor.port == 9999
    CorporateDataTable.reset_instance()
    CorporateLogTable.reset_instance()
