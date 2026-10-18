"""Tests del patrón Observer."""

from __future__ import annotations

import socket
from typing import Any

from corporate_data_server.observer import (
    CON_SUSCRIPTORES,
    SIN_SUSCRIPTORES,
    Observer,
    SocketObserver,
    Subject,
)
from corporate_data_server.protocol import decode


class ObservadorDePrueba(Observer):
    """Observador que guarda los mensajes recibidos."""

    def __init__(self) -> None:
        """Arranca sin mensajes."""
        self.recibidos: list[dict[str, Any]] = []
        self.cerrado = False

    def update(self, message: dict[str, Any]) -> None:
        """Guarda el mensaje."""
        self.recibidos.append(message)

    def close(self) -> None:
        """Marca el observador como cerrado."""
        self.cerrado = True


class ObservadorCaido(ObservadorDePrueba):
    """Observador cuyo envío siempre falla, como un socket desconectado."""

    def update(self, message: dict[str, Any]) -> None:
        """Simula un socket caído."""
        raise ConnectionResetError("cliente desconectado")


def test_arranca_sin_suscriptores() -> None:
    """Un sujeto nuevo está en el estado SinSuscriptores."""
    sujeto = Subject()
    assert sujeto.state == SIN_SUSCRIPTORES
    assert sujeto.count == 0


def test_subscribe_pasa_a_con_suscriptores() -> None:
    """Al agregar un suscriptor pasa al estado ConSuscriptores."""
    sujeto = Subject()
    sujeto.attach(ObservadorDePrueba())
    assert sujeto.state == CON_SUSCRIPTORES
    assert sujeto.count == 1


def test_notify_llega_a_todos_los_suscriptores() -> None:
    """Cada suscriptor recibe el mensaje notificado."""
    sujeto = Subject()
    observadores = [ObservadorDePrueba() for _ in range(3)]
    for obs in observadores:
        sujeto.attach(obs)
    enviados = sujeto.notify({"id": "X"})
    assert enviados == 3
    for obs in observadores:
        assert obs.recibidos == [{"id": "X"}]


def test_notify_sin_suscriptores_no_falla() -> None:
    """Notificar sin suscriptores no hace nada y devuelve 0."""
    assert Subject().notify({"id": "X"}) == 0


def test_detach_quita_al_suscriptor() -> None:
    """Un suscriptor quitado ya no recibe notificaciones."""
    sujeto = Subject()
    obs = ObservadorDePrueba()
    sujeto.attach(obs)
    sujeto.detach(obs)
    sujeto.detach(obs)  # quitar dos veces no da error
    sujeto.notify({"id": "X"})
    assert obs.recibidos == []
    assert sujeto.state == SIN_SUSCRIPTORES


def test_socket_caido_se_quita_y_quedan_los_demas() -> None:
    """Un suscriptor que falla se elimina; el resto sigue recibiendo."""
    sujeto = Subject()
    sano = ObservadorDePrueba()
    caido = ObservadorCaido()
    sujeto.attach(sano)
    sujeto.attach(caido)
    assert sujeto.notify({"id": "X"}) == 1
    assert caido.cerrado
    assert sujeto.count == 1
    assert sujeto.state == CON_SUSCRIPTORES
    sujeto.notify({"id": "Y"})
    assert sano.recibidos == [{"id": "X"}, {"id": "Y"}]


def test_si_caen_todos_vuelve_a_sin_suscriptores() -> None:
    """Si fallan todos los envíos, la lista queda vacía."""
    sujeto = Subject()
    sujeto.attach(ObservadorCaido())
    sujeto.notify({"id": "X"})
    assert sujeto.state == SIN_SUSCRIPTORES


def test_close_all_cierra_y_vacia() -> None:
    """Al detener el servidor se cierran todos los suscriptores."""
    sujeto = Subject()
    observadores = [ObservadorDePrueba() for _ in range(2)]
    for obs in observadores:
        sujeto.attach(obs)
    sujeto.close_all()
    assert all(obs.cerrado for obs in observadores)
    assert sujeto.state == SIN_SUSCRIPTORES


def test_socket_observer_envia_json_por_el_socket() -> None:
    """SocketObserver escribe el mensaje como una línea JSON en el socket."""
    servidor, cliente = socket.socketpair()
    try:
        obs = SocketObserver(servidor, client_uuid="CPU-1")
        obs.update({"id": "UADER-FCyT-IS2"})
        linea = cliente.makefile("rb").readline()
        assert decode(linea) == {"id": "UADER-FCyT-IS2"}
        assert obs.client_uuid == "CPU-1"
    finally:
        servidor.close()
        cliente.close()


def test_socket_observer_cerrado_lanza_oserror() -> None:
    """Enviar por un socket cerrado produce OSError, que Subject maneja."""
    servidor, cliente = socket.socketpair()
    obs = SocketObserver(servidor, client_uuid="CPU-1")
    obs.close()
    cliente.close()
    sujeto = Subject()
    sujeto.attach(obs)
    assert sujeto.notify({"id": "X"}) == 0
    assert sujeto.count == 0
