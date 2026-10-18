"""Acceso físico a las tablas de DynamoDB, cada una bajo el patrón Singleton.

``CorporateDataTable`` lee y escribe los datos corporativos y
``CorporateLogTable`` registra la pista de auditoría. Las dos usan
``SingletonMeta``, así que el servidor abre una sola conexión por tabla.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

import boto3

from corporate_data_server.singleton import SingletonMeta

DATA_TABLE_NAME = "CorporateData"
LOG_TABLE_NAME = "CorporateLog"

CORPORATE_FIELDS = (
    "cp",
    "CUIT",
    "domicilio",
    "idreq",
    "idSeq",
    "localidad",
    "provincia",
    "sede",
    "seqID",
    "telefono",
    "web",
)


def connect_table(table_name: str) -> Any:
    """Devuelve el objeto de boto3 que representa una tabla de DynamoDB."""
    dynamodb: Any = boto3.resource("dynamodb")
    return dynamodb.Table(table_name)


class CorporateDataTable(metaclass=SingletonMeta):
    """Acceso único a la tabla CorporateData."""

    def __init__(self, table: Any | None = None) -> None:
        """Conecta con la tabla; en los tests se recibe una tabla simulada."""
        self._table = table if table is not None else connect_table(DATA_TABLE_NAME)

    def get(self, item_id: str) -> dict[str, Any] | None:
        """Devuelve el registro con ese id, o None si no existe."""
        response = self._table.get_item(Key={"id": item_id})
        item: dict[str, Any] | None = response.get("Item")
        return item

    def list_all(self) -> list[dict[str, Any]]:
        """Devuelve todos los registros de la tabla, recorriendo cada página."""
        items: list[dict[str, Any]] = []
        kwargs: dict[str, Any] = {}
        while True:
            response = self._table.scan(**kwargs)
            items.extend(response.get("Items", []))
            last_key = response.get("LastEvaluatedKey")
            if last_key is None:
                return items
            kwargs["ExclusiveStartKey"] = last_key

    def upsert(self, item_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        """Actualiza o crea un registro y devuelve cómo quedó guardado.

        Si el id existe, solo cambian los campos informados. Si no existe, se
        crea un registro nuevo con los campos faltantes en blanco.
        """
        existing = self.get(item_id)
        if existing is None:
            record: dict[str, Any] = {field: "" for field in CORPORATE_FIELDS}
        else:
            record = dict(existing)
        record.update(fields)
        record["id"] = item_id
        self._table.put_item(Item=record)
        return record


class CorporateLogTable(metaclass=SingletonMeta):
    """Acceso único a la tabla CorporateLog (pista de auditoría)."""

    def __init__(self, table: Any | None = None) -> None:
        """Conecta con la tabla; en los tests se recibe una tabla simulada."""
        self._table = table if table is not None else connect_table(LOG_TABLE_NAME)

    def log(
        self,
        client_uuid: str,
        session_id: str,
        action: str,
        item_id: str | None = None,
    ) -> dict[str, Any]:
        """Registra una acción en la auditoría y devuelve el registro creado."""
        record: dict[str, Any] = {
            "id": str(uuid.uuid4()),
            "CPUid": client_uuid,
            "sessionid": session_id,
            "action": action,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        if item_id is not None:
            record["item_id"] = item_id
        self._table.put_item(Item=record)
        return record
