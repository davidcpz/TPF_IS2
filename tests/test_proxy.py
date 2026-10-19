"""Tests del patrón Proxy."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

from corporate_data_server.observer import Observer, Subject
from corporate_data_server.proxy import CorporateDataProxy, validate
from corporate_data_server.tables import CorporateDataTable, CorporateLogTable
from fakes import FakeTable

SESION = "SES-1"
CLIENTE = "CPU-1"
REGISTRO = {"id": "UADER-FCyT-IS2", "sede": "FCyT", "telefono": "03442 43-1442"}


class TablaConHistorial(FakeTable):
    """FakeTable que anota en una lista compartida cada operación recibida."""

    def __init__(self, nombre: str, historial: list[str]) -> None:
        """Guarda el nombre de la tabla y la lista donde se anotan los accesos."""
        super().__init__()
        self.nombre = nombre
        self.historial = historial

    def get_item(self, Key: dict[str, str]) -> dict[str, Any]:  # noqa: N803
        """Anota la lectura y la delega."""
        self.historial.append(f"{self.nombre}.get_item")
        return super().get_item(Key)

    def put_item(self, Item: dict[str, Any]) -> dict[str, Any]:  # noqa: N803
        """Anota la escritura y la delega."""
        self.historial.append(f"{self.nombre}.put_item")
        return super().put_item(Item)

    def scan(self, **kwargs: Any) -> dict[str, Any]:
        """Anota el recorrido y lo delega."""
        self.historial.append(f"{self.nombre}.scan")
        return super().scan(**kwargs)


class Suscriptor(Observer):
    """Observador de prueba que guarda lo que recibe."""

    def __init__(self) -> None:
        """Arranca sin mensajes."""
        self.recibidos: list[dict[str, Any]] = []

    def update(self, message: dict[str, Any]) -> None:
        """Guarda el mensaje."""
        self.recibidos.append(message)


class Entorno:
    """Proxy armado con tablas simuladas, listo para cada test."""

    def __init__(self) -> None:
        """Crea tablas, sujeto y proxy, con un registro inicial."""
        self.historial: list[str] = []
        self.data = TablaConHistorial("CorporateData", self.historial)
        self.log = TablaConHistorial("CorporateLog", self.historial)
        self.data.items[REGISTRO["id"]] = dict(REGISTRO)
        self.sujeto = Subject()
        self.proxy = CorporateDataProxy(
            CorporateDataTable(self.data), CorporateLogTable(self.log), self.sujeto
        )

    def logs(self) -> list[dict[str, Any]]:
        """Devuelve los registros de auditoría guardados."""
        return list(self.log.items.values())


@pytest.fixture
def entorno() -> Iterator[Entorno]:
    """Entrega un entorno nuevo y limpia los Singleton al terminar."""
    CorporateDataTable.reset_instance()
    CorporateLogTable.reset_instance()
    yield Entorno()
    CorporateDataTable.reset_instance()
    CorporateLogTable.reset_instance()


def pedido(action: str, **extra: Any) -> dict[str, Any]:
    """Arma un pedido como el que envía singletonclient."""
    return {"UUID": CLIENTE, "ACTION": action, **extra}


# ---------- Validación ----------


@pytest.mark.parametrize(
    ("request_data", "texto"),
    [
        ("no soy un objeto", "objeto JSON"),
        ({"ACTION": "list"}, "UUID"),
        ({"UUID": "  ", "ACTION": "list"}, "UUID"),
        ({"UUID": CLIENTE}, "Acción inválida"),
        ({"UUID": CLIENTE, "ACTION": "borrar"}, "Acción inválida"),
        ({"UUID": CLIENTE, "ACTION": "get"}, "requiere el campo ID"),
        ({"UUID": CLIENTE, "ACTION": "set", "ID": ""}, "requiere el campo ID"),
    ],
)
def test_pedidos_invalidos_devuelven_error_sin_tocar_tablas(
    entorno: Entorno, request_data: Any, texto: str
) -> None:
    """Un pedido inválido se rechaza antes de llegar a cualquier tabla."""
    respuesta = entorno.proxy.process(request_data, SESION)
    assert texto in respuesta["Error"]
    assert entorno.historial == []


def test_la_accion_no_distingue_mayusculas() -> None:
    """ACTION acepta 'GET' igual que 'get'."""
    assert validate({"UUID": CLIENTE, "ACTION": "GET", "ID": "X"}) == (
        "get",
        CLIENTE,
        "X",
    )


def test_list_no_requiere_id() -> None:
    """Para list el ID vuelve vacío."""
    assert validate({"UUID": CLIENTE, "ACTION": "list"}) == ("list", CLIENTE, "")


# ---------- get ----------


def test_get_devuelve_el_registro_y_audita(entorno: Entorno) -> None:
    """Get responde el registro y deja constancia con el ID consultado."""
    respuesta = entorno.proxy.process(pedido("get", ID=REGISTRO["id"]), SESION)
    assert respuesta == REGISTRO
    (log,) = entorno.logs()
    assert log["action"] == "get"
    assert log["item_id"] == REGISTRO["id"]
    assert log["CPUid"] == CLIENTE
    assert log["sessionid"] == SESION


def test_get_inexistente_devuelve_error_pero_audita(entorno: Entorno) -> None:
    """Pedir un ID que no existe responde Error y queda registrado igual."""
    respuesta = entorno.proxy.process(pedido("get", ID="NO-EXISTE"), SESION)
    assert "NO-EXISTE" in respuesta["Error"]
    assert entorno.logs()[0]["item_id"] == "NO-EXISTE"


# ---------- list ----------


def test_list_devuelve_todos_los_registros(entorno: Entorno) -> None:
    """List responde un array con todos los registros."""
    entorno.data.items["OTRO"] = {"id": "OTRO"}
    respuesta = entorno.proxy.process(pedido("list"), SESION)
    assert sorted(r["id"] for r in respuesta) == ["OTRO", REGISTRO["id"]]
    assert entorno.logs()[0]["action"] == "list"


# ---------- set ----------


def test_set_actualiza_solo_lo_informado(entorno: Entorno) -> None:
    """Set modifica los campos enviados y conserva el resto."""
    respuesta = entorno.proxy.process(
        pedido("set", ID=REGISTRO["id"], telefono="0800-123"), SESION
    )
    assert respuesta["telefono"] == "0800-123"
    assert respuesta["sede"] == "FCyT"
    assert "UUID" not in respuesta
    assert "ACTION" not in respuesta
    assert entorno.data.items[REGISTRO["id"]] == respuesta


def test_set_de_id_nuevo_crea_el_registro(entorno: Entorno) -> None:
    """Set con un ID inexistente crea el registro."""
    respuesta = entorno.proxy.process(pedido("set", ID="NUEVO", sede="FCEDU"), SESION)
    assert respuesta["id"] == "NUEVO"
    assert respuesta["sede"] == "FCEDU"
    assert respuesta["telefono"] == ""


def test_set_notifica_a_los_suscriptores(entorno: Entorno) -> None:
    """Después de un set, cada suscriptor recibe el registro modificado."""
    suscriptores = [Suscriptor(), Suscriptor()]
    for s in suscriptores:
        entorno.sujeto.attach(s)
    respuesta = entorno.proxy.process(
        pedido("set", ID=REGISTRO["id"], cp="3260"), SESION
    )
    for s in suscriptores:
        assert s.recibidos == [respuesta]


def test_get_y_list_no_notifican(entorno: Entorno) -> None:
    """Solo set dispara notificaciones."""
    suscriptor = Suscriptor()
    entorno.sujeto.attach(suscriptor)
    entorno.proxy.process(pedido("get", ID=REGISTRO["id"]), SESION)
    entorno.proxy.process(pedido("list"), SESION)
    assert suscriptor.recibidos == []


# ---------- subscribe ----------


def test_subscribe_registra_y_audita(entorno: Entorno) -> None:
    """Subscribe agrega al suscriptor y queda en la auditoría."""
    respuesta = entorno.proxy.process(pedido("subscribe"), SESION, Suscriptor())
    assert respuesta == {"status": "subscribed", "UUID": CLIENTE}
    assert entorno.sujeto.count == 1
    assert entorno.logs()[0]["action"] == "subscribe"


def test_subscribe_sin_conexion_da_error(entorno: Entorno) -> None:
    """Sin observador (conexión) no se puede suscribir."""
    respuesta = entorno.proxy.process(pedido("subscribe"), SESION)
    assert "Error" in respuesta
    assert entorno.sujeto.count == 0


# ---------- Comportamiento de Proxy ----------


@pytest.mark.parametrize(
    ("request_data", "acceso"),
    [
        (pedido("get", ID=REGISTRO["id"]), "CorporateData.get_item"),
        (pedido("list"), "CorporateData.scan"),
        (pedido("set", ID=REGISTRO["id"], cp="1"), "CorporateData.get_item"),
    ],
)
def test_audita_antes_de_acceder_a_los_datos(
    entorno: Entorno, request_data: dict[str, Any], acceso: str
) -> None:
    """El proxy escribe en CorporateLog antes de tocar CorporateData."""
    entorno.proxy.process(request_data, SESION)
    assert entorno.historial[0] == "CorporateLog.put_item"
    assert entorno.historial[1] == acceso


def test_error_de_base_de_datos_devuelve_error(entorno: Entorno) -> None:
    """Si DynamoDB falla, el cliente recibe un Error y el proxy no se cae."""

    def falla(**_: Any) -> dict[str, Any]:
        raise RuntimeError("DynamoDB no disponible")

    entorno.data.scan = falla  # type: ignore[method-assign]
    respuesta = entorno.proxy.process(pedido("list"), SESION)
    assert respuesta == {"Error": "Error de acceso a la base de datos"}
