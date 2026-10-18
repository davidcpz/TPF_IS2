"""Tests del patrón Singleton."""

from __future__ import annotations

import threading
from collections.abc import Iterator

import pytest

from corporate_data_server.singleton import SingletonMeta


class Contador(metaclass=SingletonMeta):
    """Clase de prueba que cuenta cuántas veces se ejecutó su constructor."""

    creaciones = 0

    def __init__(self) -> None:
        """Incrementa el contador de creaciones."""
        Contador.creaciones += 1


class Otra(metaclass=SingletonMeta):
    """Segunda clase de prueba, independiente de Contador."""


@pytest.fixture(autouse=True)
def instancias_limpias() -> Iterator[None]:
    """Arranca cada test sin instancias previas."""
    Contador.reset_instance()
    Otra.reset_instance()
    Contador.creaciones = 0
    yield


def test_dos_llamadas_devuelven_la_misma_instancia() -> None:
    """Dos creaciones seguidas devuelven exactamente el mismo objeto."""
    assert Contador() is Contador()


def test_el_constructor_se_ejecuta_una_sola_vez() -> None:
    """El __init__ corre solo en la primera creación."""
    Contador()
    Contador()
    Contador()
    assert Contador.creaciones == 1


def test_cada_clase_tiene_su_propia_instancia() -> None:
    """Dos clases distintas no comparten la instancia."""
    assert Contador() is not Otra()


def test_reset_permite_crear_una_instancia_nueva() -> None:
    """Después de reset_instance se crea un objeto nuevo."""
    primera = Contador()
    Contador.reset_instance()
    assert Contador() is not primera


def test_es_seguro_con_varios_hilos() -> None:
    """Veinte hilos simultáneos obtienen la misma instancia."""
    resultados: list[Contador] = []

    def crear() -> None:
        resultados.append(Contador())

    hilos = [threading.Thread(target=crear) for _ in range(20)]
    for hilo in hilos:
        hilo.start()
    for hilo in hilos:
        hilo.join()

    assert len({id(obj) for obj in resultados}) == 1
    assert Contador.creaciones == 1