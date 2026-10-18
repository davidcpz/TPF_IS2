"""Tests de las clases de acceso a las tablas."""

from __future__ import annotations

import re
from collections.abc import Iterator
from typing import Any

import pytest

from corporate_data_server import tables
from corporate_data_server.tables import (
    CORPORATE_FIELDS,
    CorporateDataTable,
    CorporateLogTable,
)
from fakes import FakeTable


@pytest.fixture(autouse=True)
def instancias_limpias() -> Iterator[None]:
    """Cada test arranca sin instancias Singleton previas."""
    CorporateDataTable.reset_instance()
    CorporateLogTable.reset_instance()
    yield
    CorporateDataTable.reset_instance()
    CorporateLogTable.reset_instance()


# ---------- Patrón Singleton ----------


def test_corporate_data_es_singleton() -> None:
    """Dos accesos a CorporateDataTable devuelven el mismo objeto."""
    assert CorporateDataTable(FakeTable()) is CorporateDataTable()


def test_corporate_log_es_singleton() -> None:
    """Dos accesos a CorporateLogTable devuelven el mismo objeto."""
    assert CorporateLogTable(FakeTable()) is CorporateLogTable()


def test_las_dos_tablas_son_instancias_distintas() -> None:
    """Cada tabla tiene su propia instancia única."""
    assert CorporateDataTable(FakeTable()) is not CorporateLogTable(FakeTable())


def test_sin_tabla_se_conecta_a_dynamodb(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sin tabla simulada, se pide a boto3 la tabla con el nombre correcto."""
    pedidas: list[str] = []

    class FakeResource:
        def Table(self, name: str) -> FakeTable:  # noqa: N802
            pedidas.append(name)
            return FakeTable()

    def fake_resource(service: str) -> FakeResource:
        assert service == "dynamodb"
        return FakeResource()

    monkeypatch.setattr(tables.boto3, "resource", fake_resource)
    CorporateDataTable()
    CorporateLogTable()
    assert pedidas == ["CorporateData", "CorporateLog"]


# ---------- CorporateDataTable ----------


def test_get_devuelve_el_registro() -> None:
    """El método get devuelve el registro guardado con ese id."""
    fake = FakeTable()
    fake.items["UADER-FCyT-IS2"] = {"id": "UADER-FCyT-IS2", "sede": "FCyT"}
    assert CorporateDataTable(fake).get("UADER-FCyT-IS2") == {
        "id": "UADER-FCyT-IS2",
        "sede": "FCyT",
    }


def test_get_de_id_inexistente_devuelve_none() -> None:
    """Pedir con get un id que no existe devuelve None."""
    assert CorporateDataTable(FakeTable()).get("NO-EXISTE") is None


def test_list_all_recorre_todas_las_paginas() -> None:
    """list_all junta los registros de todas las páginas del scan."""
    fake = FakeTable(page_size=2)
    for i in range(5):
        fake.items[f"id-{i}"] = {"id": f"id-{i}"}
    ids = [item["id"] for item in CorporateDataTable(fake).list_all()]
    assert sorted(ids) == [f"id-{i}" for i in range(5)]


def test_list_all_de_tabla_vacia() -> None:
    """list_all de una tabla vacía devuelve una lista vacía."""
    assert CorporateDataTable(FakeTable()).list_all() == []


def test_upsert_actualiza_solo_los_campos_informados() -> None:
    """Si el id existe, los campos no informados conservan su valor."""
    fake = FakeTable()
    fake.items["X"] = {"id": "X", "sede": "FCyT", "telefono": "111"}
    resultado = CorporateDataTable(fake).upsert("X", {"telefono": "222"})
    assert resultado == {"id": "X", "sede": "FCyT", "telefono": "222"}
    assert fake.items["X"] == resultado


def test_upsert_crea_registro_nuevo_con_campos_en_blanco() -> None:
    """Si el id no existe, se crea con los campos faltantes en blanco."""
    fake = FakeTable()
    resultado = CorporateDataTable(fake).upsert("NUEVO", {"sede": "FCyT"})
    assert resultado["id"] == "NUEVO"
    assert resultado["sede"] == "FCyT"
    for campo in CORPORATE_FIELDS:
        if campo != "sede":
            assert resultado[campo] == ""
    assert fake.items["NUEVO"] == resultado


def test_upsert_no_permite_cambiar_el_id() -> None:
    """Aunque los datos traigan otro id, se respeta el id indicado."""
    fake = FakeTable()
    resultado = CorporateDataTable(fake).upsert("A", {"id": "B", "sede": "X"})
    assert resultado["id"] == "A"
    assert "B" not in fake.items


# ---------- CorporateLogTable ----------


def _unico_registro(fake: FakeTable) -> dict[str, Any]:
    assert len(fake.items) == 1
    return next(iter(fake.items.values()))


def test_log_guarda_los_campos_de_auditoria() -> None:
    """El método log guarda UUID del cliente, sesión, acción y timestamp."""
    fake = FakeTable()
    CorporateLogTable(fake).log("CPU-1", "SES-1", "list")
    registro = _unico_registro(fake)
    assert registro["CPUid"] == "CPU-1"
    assert registro["sessionid"] == "SES-1"
    assert registro["action"] == "list"
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", registro["timestamp"])
    assert "item_id" not in registro


def test_log_con_id_solicitado() -> None:
    """Cuando la acción involucra un registro, se guarda su id."""
    fake = FakeTable()
    CorporateLogTable(fake).log("CPU-1", "SES-1", "get", item_id="UADER-FCyT-IS2")
    assert _unico_registro(fake)["item_id"] == "UADER-FCyT-IS2"


def test_cada_log_tiene_un_id_unico() -> None:
    """Cada registro de auditoría recibe un id distinto."""
    fake = FakeTable()
    log = CorporateLogTable(fake)
    primero = log.log("CPU-1", "SES-1", "get")
    segundo = log.log("CPU-1", "SES-1", "get")
    assert primero["id"] != segundo["id"]
    assert len(fake.items) == 2
