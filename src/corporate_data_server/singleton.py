"""Patrón Singleton implementado con una metaclase.

Cualquier clase que use ``SingletonMeta`` como metaclase tiene una única
instancia en todo el programa: la primera llamada la crea y las siguientes
devuelven esa misma instancia.
"""

from __future__ import annotations

import threading
from typing import Any

# Instancias únicas ya creadas, una por clase, y el candado que las protege.
# Se guardan a nivel de módulo (y no como atributos de la metaclase) para que
# no aparezcan como si fueran atributos de cada clase Singleton.
_instances: dict[type, Any] = {}
_lock = threading.Lock()


class SingletonMeta(type):
    """Metaclase que garantiza una única instancia por clase.

    Es segura para hilos: si dos hilos piden la instancia al mismo tiempo,
    un candado (lock) asegura que solo uno de ellos la cree.
    """

    def __call__(cls, *args: Any, **kwargs: Any) -> Any:
        """Devuelve la instancia única de la clase, creándola la primera vez."""
        with _lock:
            if cls not in _instances:
                _instances[cls] = super().__call__(*args, **kwargs)
        return _instances[cls]

    def reset_instance(cls) -> None:
        """Descarta la instancia guardada; se usa en los tests."""
        with _lock:
            _instances.pop(cls, None)
