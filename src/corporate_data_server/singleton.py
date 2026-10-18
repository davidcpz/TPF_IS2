"""Patrón Singleton implementado con una metaclase.

Cualquier clase que use ``SingletonMeta`` como metaclase tiene una única
instancia en todo el programa: la primera llamada la crea y las siguientes
devuelven esa misma instancia.
"""

from __future__ import annotations

import threading
from typing import Any, ClassVar


class SingletonMeta(type):
    """Metaclase que garantiza una única instancia por clase.

    Es segura para hilos: si dos hilos piden la instancia al mismo tiempo,
    un candado (lock) asegura que solo uno de ellos la cree.
    """

    _instances: ClassVar[dict[type, Any]] = {}
    _lock: ClassVar[threading.Lock] = threading.Lock()

    def __call__(cls, *args: Any, **kwargs: Any) -> Any:
        """Devuelve la instancia única de la clase, creándola la primera vez."""
        with cls._lock:
            if cls not in cls._instances:
                cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]

    def reset_instance(cls) -> None:
        """Descarta la instancia guardada; se usa en los tests."""
        with cls._lock:
            cls._instances.pop(cls, None)