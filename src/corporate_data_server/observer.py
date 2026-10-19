"""Patrón Observer: notificación de cambios a los clientes suscriptos.

``Subject`` mantiene la lista de observadores y les avisa cada cambio.
``SocketObserver`` es un observador concreto: un cliente conectado por socket.
"""

from __future__ import annotations

import socket
import threading
from abc import ABC, abstractmethod
from typing import Any

from corporate_data_server.protocol import encode

SIN_SUSCRIPTORES = "SinSuscriptores"
CON_SUSCRIPTORES = "ConSuscriptores"


class Observer(ABC):
    """Interfaz que debe cumplir todo observador."""

    @abstractmethod
    def update(self, message: dict[str, Any]) -> None:
        """Recibe la notificación de un cambio."""

    def close(self) -> None:  # noqa: B027
        """Libera los recursos del observador; por defecto no hace nada."""


class SocketObserver(Observer):
    """Observador que reenvía cada notificación por un socket TCP."""

    def __init__(self, conn: socket.socket, client_uuid: str) -> None:
        """Guarda el socket del cliente suscripto y su identificación."""
        self.conn = conn
        self.client_uuid = client_uuid

    def update(self, message: dict[str, Any]) -> None:
        """Envía el mensaje al cliente; si el socket cayó, lanza OSError."""
        self.conn.sendall(encode(message))

    def close(self) -> None:
        """Avisa el corte al cliente y cierra el socket."""
        try:
            self.conn.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass  # el socket ya estaba cortado
        self.conn.close()


class Subject:
    """Sujeto observado: guarda los suscriptores y les notifica los cambios.

    Sus estados siguen el diagrama de estados del observer:
    SinSuscriptores, ConSuscriptores y, mientras envía, Notificando.
    """

    def __init__(self) -> None:
        """Crea el sujeto sin suscriptores."""
        self._observers: list[Observer] = []
        self._lock = threading.Lock()

    @property
    def state(self) -> str:
        """Estado actual según el diagrama: SinSuscriptores o ConSuscriptores."""
        with self._lock:
            return CON_SUSCRIPTORES if self._observers else SIN_SUSCRIPTORES

    @property
    def count(self) -> int:
        """Cantidad de suscriptores registrados."""
        with self._lock:
            return len(self._observers)

    def attach(self, observer: Observer) -> None:
        """Agrega un suscriptor a la lista."""
        with self._lock:
            self._observers.append(observer)

    def detach(self, observer: Observer) -> None:
        """Quita un suscriptor de la lista, si estaba."""
        with self._lock:
            if observer in self._observers:
                self._observers.remove(observer)

    def notify(self, message: dict[str, Any]) -> int:
        """Envía el mensaje a todos los suscriptores (estado Notificando).

        Los suscriptores cuyo envío falla se quitan de la lista y se cierran.
        Devuelve la cantidad de suscriptores que recibieron el mensaje.
        """
        with self._lock:
            observers = list(self._observers)
        failed: list[Observer] = []
        for observer in observers:
            try:
                observer.update(message)
            except OSError:
                failed.append(observer)
        for observer in failed:
            self.detach(observer)
            try:
                observer.close()
            except OSError:
                pass
        return len(observers) - len(failed)

    def close_all(self) -> None:
        """Cierra todos los suscriptores; se usa al detener el servidor."""
        with self._lock:
            observers = list(self._observers)
            self._observers.clear()
        for observer in observers:
            try:
                observer.close()
            except OSError:
                pass
