"""Dobles de prueba: reemplazan a DynamoDB para que los tests no usen AWS."""

from __future__ import annotations

from typing import Any


class FakeTable:
    """Tabla en memoria con los mismos métodos que usa el código de boto3."""

    def __init__(self, page_size: int = 100) -> None:
        """Crea la tabla vacía; page_size simula la paginación de scan."""
        self.items: dict[str, dict[str, Any]] = {}
        self.page_size = page_size

    def get_item(self, Key: dict[str, str]) -> dict[str, Any]:  # noqa: N803
        """Devuelve {'Item': ...} si existe, o un diccionario sin 'Item'."""
        item = self.items.get(Key["id"])
        return {"Item": dict(item)} if item is not None else {}

    def put_item(self, Item: dict[str, Any]) -> dict[str, Any]:  # noqa: N803
        """Guarda (o reemplaza) el registro completo."""
        self.items[Item["id"]] = dict(Item)
        return {}

    def scan(self, **kwargs: Any) -> dict[str, Any]:
        """Devuelve una página de registros, como hace DynamoDB."""
        keys = sorted(self.items)
        start = kwargs.get("ExclusiveStartKey")
        if start is not None:
            keys = [k for k in keys if k > start["id"]]
        page = keys[: self.page_size]
        response: dict[str, Any] = {"Items": [dict(self.items[k]) for k in page]}
        if len(keys) > self.page_size:
            response["LastEvaluatedKey"] = {"id": page[-1]}
        return response
