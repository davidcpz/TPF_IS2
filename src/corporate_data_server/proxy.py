"""Patrón Proxy: intermediario entre los clientes y los datos corporativos.

Ningún cliente accede a las tablas directamente. Cada pedido pasa por
``CorporateDataProxy``, que lo valida, lo registra en la auditoría y recién
después lo delega en la tabla que corresponde (ver diagrama de actividad).
"""

from __future__ import annotations

import logging
from typing import Any

from corporate_data_server.observer import Observer, Subject
from corporate_data_server.tables import CorporateDataTable, CorporateLogTable

logger = logging.getLogger(__name__)

VALID_ACTIONS = ("get", "set", "list", "subscribe")
ACTIONS_WITH_ID = ("get", "set")
REQUEST_KEYS = ("UUID", "ID", "ACTION")


class RequestError(ValueError):
    """Pedido mal formado o incompleto."""


def error_response(message: str) -> dict[str, str]:
    """Arma la respuesta de error que recibe el cliente."""
    return {"Error": message}


def validate(request: Any) -> tuple[str, str, str]:
    """Controla el pedido y devuelve (acción, UUID del cliente, ID).

    El ID vuelve vacío en las acciones que no lo usan (list y subscribe).

    Lanza RequestError si el pedido no es válido o le faltan datos mínimos.
    """
    if not isinstance(request, dict):
        raise RequestError("El pedido debe ser un objeto JSON")
    client_uuid = request.get("UUID")
    if not isinstance(client_uuid, str) or not client_uuid.strip():
        raise RequestError("Falta el UUID del cliente")
    action = request.get("ACTION")
    if not isinstance(action, str) or action.lower() not in VALID_ACTIONS:
        raise RequestError(f"Acción inválida; se espera una de {VALID_ACTIONS}")
    action = action.lower()
    item_id = request.get("ID")
    if action in ACTIONS_WITH_ID:
        if not isinstance(item_id, str) or not item_id.strip():
            raise RequestError(f"La acción '{action}' requiere el campo ID")
        return action, client_uuid, item_id
    return action, client_uuid, ""


class CorporateDataProxy:
    """Proxy de acceso a CorporateData con auditoría y notificación."""

    def __init__(
        self,
        data_table: CorporateDataTable,
        log_table: CorporateLogTable,
        subject: Subject,
    ) -> None:
        """Recibe las dos tablas (Singleton) y el sujeto del Observer."""
        self._data = data_table
        self._log = log_table
        self._subject = subject

    def process(
        self,
        request: Any,
        session_id: str,
        observer: Observer | None = None,
    ) -> Any:
        """Atiende un pedido completo y devuelve la respuesta para el cliente."""
        try:
            action, client_uuid, item_id = validate(request)
        except RequestError as exc:
            logger.debug("Pedido rechazado: %s", exc)
            return error_response(str(exc))

        logger.debug("Sesión %s: %s pedido por %s", session_id, action, client_uuid)
        try:
            if action == "subscribe":
                return self._subscribe(client_uuid, session_id, observer)
            if action == "list":
                return self._list(client_uuid, session_id)
            if action == "get":
                return self._get(client_uuid, session_id, item_id)
            return self._set(client_uuid, session_id, item_id, request)
        except Exception:
            logger.exception("Error al acceder a DynamoDB")
            return error_response("Error de acceso a la base de datos")

    def _subscribe(
        self, client_uuid: str, session_id: str, observer: Observer | None
    ) -> dict[str, str]:
        if observer is None:
            return error_response("La suscripción requiere una conexión abierta")
        self._log.log(client_uuid, session_id, "subscribe")
        self._subject.attach(observer)
        return {"status": "subscribed", "UUID": client_uuid}

    def _list(self, client_uuid: str, session_id: str) -> list[dict[str, Any]]:
        self._log.log(client_uuid, session_id, "list")
        return self._data.list_all()

    def _get(self, client_uuid: str, session_id: str, item_id: str) -> Any:
        self._log.log(client_uuid, session_id, "get", item_id=item_id)
        record = self._data.get(item_id)
        if record is None:
            return error_response(f"No existe el registro {item_id}")
        return record

    def _set(
        self,
        client_uuid: str,
        session_id: str,
        item_id: str,
        request: dict[str, Any],
    ) -> dict[str, Any]:
        self._log.log(client_uuid, session_id, "set", item_id=item_id)
        fields = {
            key: value
            for key, value in request.items()
            if key not in REQUEST_KEYS and key != "id"
        }
        record = self._data.upsert(item_id, fields)
        notified = self._subject.notify(record)
        logger.debug("Registro %s actualizado; %d notificados", item_id, notified)
        return record
