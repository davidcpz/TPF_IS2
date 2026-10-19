"""Piezas compartidas por los tests de los clientes.

pytest carga este archivo automáticamente: sus fixtures quedan disponibles
en todos los tests sin necesidad de importarlas.
"""

from __future__ import annotations

import socket
import threading
import time
from collections.abc import Callable, Iterator

import pytest

from corporate_data_server.observer import Subject
from corporate_data_server.proxy import CorporateDataProxy
from corporate_data_server.server import CorporateServer
from corporate_data_server.tables import CorporateDataTable, CorporateLogTable
from fakes import FakeTable

REGISTRO_INICIAL = {"id": "UADER-FCyT-IS2", "sede": "FCyT", "cp": "3260"}


class ServidorDePrueba:
    """Servidor real en un puerto libre, con tablas en memoria."""

    def __init__(self, port: int = 0) -> None:
        """Arma las tablas simuladas, el proxy y el servidor."""
        self.data = FakeTable()
        self.log = FakeTable()
        self.data.items[REGISTRO_INICIAL["id"]] = dict(REGISTRO_INICIAL)
        self.sujeto = Subject()
        proxy = CorporateDataProxy(
            CorporateDataTable(self.data), CorporateLogTable(self.log), self.sujeto
        )
        self.server = CorporateServer(proxy, self.sujeto, host="127.0.0.1", port=port)
        self._hilo: threading.Thread | None = None

    @property
    def port(self) -> int:
        """Puerto real en el que escucha."""
        return self.server.port

    def iniciar(self) -> None:
        """Abre el puerto y atiende en un hilo aparte."""
        self.server.start()
        self._hilo = threading.Thread(target=self.server.serve_forever, daemon=True)
        self._hilo.start()

    def detener(self) -> None:
        """Detiene el servidor y espera a que termine su hilo."""
        self.server.shutdown()
        if self._hilo is not None:
            self._hilo.join(timeout=5)


def esperar(condicion: Callable[[], bool], segundos: float = 5.0) -> bool:
    """Espera a que la condición se cumpla, como máximo unos segundos."""
    limite = time.monotonic() + segundos
    while time.monotonic() < limite:
        if condicion():
            return True
        time.sleep(0.02)
    return False


def puerto_libre() -> int:
    """Devuelve un puerto donde no hay nadie escuchando."""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.fixture
def servidor() -> Iterator[ServidorDePrueba]:
    """Servidor de prueba iniciado; se detiene al terminar el test."""
    CorporateDataTable.reset_instance()
    CorporateLogTable.reset_instance()
    srv = ServidorDePrueba()
    srv.iniciar()
    yield srv
    srv.detener()
    CorporateDataTable.reset_instance()
    CorporateLogTable.reset_instance()
