"""Servidor TCP SingletonProxyObserver.

Acepta conexiones en un puerto (por defecto 8080). Cada conexión trae un
pedido JSON de una línea; el servidor lo pasa al proxy y responde. Las
conexiones de tipo ``subscribe`` quedan abiertas para recibir notificaciones.
"""

from __future__ import annotations

import argparse
import logging
import socket
import threading
import uuid
from collections.abc import Sequence
from typing import Any

from corporate_data_server.cli import configure_logging, port_type
from corporate_data_server.observer import SocketObserver, Subject
from corporate_data_server.protocol import decode, encode
from corporate_data_server.proxy import CorporateDataProxy, error_response
from corporate_data_server.tables import CorporateDataTable, CorporateLogTable

logger = logging.getLogger(__name__)

DEFAULT_HOST = ""  # todas las interfaces de red: *:8080
DEFAULT_PORT = 8080
MAX_REQUEST_BYTES = 65536
REQUEST_TIMEOUT = 30.0
ACCEPT_TIMEOUT = 1.0


class ServerError(RuntimeError):
    """El servidor no pudo iniciarse (por ejemplo, el puerto ya está en uso)."""


def _is_subscribe(request: Any) -> bool:
    """Indica si el pedido es una suscripción."""
    return (
        isinstance(request, dict)
        and str(request.get("ACTION", "")).lower() == "subscribe"
    )


class CorporateServer:
    """Servidor de aplicaciones: recibe pedidos por TCP y los delega en el proxy."""

    def __init__(
        self,
        proxy: CorporateDataProxy,
        subject: Subject,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
    ) -> None:
        """Guarda el proxy, el sujeto del observer y la dirección de escucha."""
        self._proxy = proxy
        self._subject = subject
        self._host = host
        self._port = port
        self._sock: socket.socket | None = None
        self._running = threading.Event()

    @property
    def port(self) -> int:
        """Puerto en el que escucha el servidor."""
        if self._sock is None:
            return self._port
        return int(self._sock.getsockname()[1])

    def start(self) -> None:
        """Abre el puerto. Lanza ServerError si ya está en uso."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        exclusive = getattr(socket, "SO_EXCLUSIVEADDRUSE", None)
        if exclusive is not None:
            # Solo existe en Windows: impide que otro servidor use el mismo puerto.
            sock.setsockopt(socket.SOL_SOCKET, exclusive, 1)
        try:
            sock.bind((self._host, self._port))
            sock.listen()
        except OSError as exc:
            sock.close()
            raise ServerError(
                f"No se pudo abrir el puerto {self._port}: {exc}"
            ) from exc
        sock.settimeout(ACCEPT_TIMEOUT)
        self._sock = sock
        self._running.set()
        logger.info("Servidor escuchando en el puerto %d", self.port)

    def serve_forever(self) -> None:
        """Atiende conexiones hasta que se llame a shutdown()."""
        if self._sock is None:
            self.start()
        while self._running.is_set() and self._sock is not None:
            try:
                conn, address = self._sock.accept()
            except TimeoutError:
                continue
            except OSError:
                break
            hilo = threading.Thread(
                target=self.handle_client, args=(conn, address), daemon=True
            )
            hilo.start()

    def shutdown(self) -> None:
        """Detiene el servidor y cierra las conexiones de los suscriptores."""
        self._running.clear()
        if self._sock is not None:
            self._sock.close()
            self._sock = None
        self._subject.close_all()
        logger.info("Servidor detenido")

    def handle_client(self, conn: socket.socket, address: Any) -> None:
        """Atiende una conexión: lee el pedido, responde y cierra o la mantiene."""
        session_id = str(uuid.uuid4())
        logger.debug("Conexión de %s (sesión %s)", address, session_id)
        keep_open = False
        try:
            conn.settimeout(REQUEST_TIMEOUT)
            with conn.makefile("rb") as reader:
                line = reader.readline(MAX_REQUEST_BYTES)
            if not line.strip():
                return
            observer: SocketObserver | None = None
            try:
                request = decode(line)
            except ValueError:
                response: Any = error_response("El mensaje no es un JSON válido")
            else:
                logger.debug("Pedido recibido: %s", request)
                if _is_subscribe(request):
                    observer = SocketObserver(conn, str(request.get("UUID")))
                response = self._proxy.process(request, session_id, observer)
                keep_open = (
                    observer is not None
                    and isinstance(response, dict)
                    and response.get("status") == "subscribed"
                )
            conn.sendall(encode(response))
            logger.debug("Respuesta enviada a %s", address)
            if keep_open and observer is not None:
                self._wait_until_closed(observer)
        except OSError as exc:
            logger.debug("Conexión con %s interrumpida: %s", address, exc)
        finally:
            if not keep_open:
                conn.close()

    def _wait_until_closed(self, observer: SocketObserver) -> None:
        """Mantiene abierta la conexión del suscriptor hasta que el cliente corte."""
        observer.conn.settimeout(None)
        try:
            while observer.conn.recv(1024):
                pass
        except OSError:
            pass
        finally:
            self._subject.detach(observer)
            observer.close()
            logger.debug("Suscriptor %s desconectado", observer.client_uuid)


# ---------- Programa principal ----------


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Interpreta los argumentos: {-p=port} {-v}."""
    parser = argparse.ArgumentParser(
        prog="singletonproxyobserver.py",
        description="Servidor de datos corporativos (Singleton, Proxy, Observer).",
    )
    parser.add_argument("-p", "--port", type=port_type, default=DEFAULT_PORT)
    parser.add_argument("-v", "--verbose", action="store_true")
    return parser.parse_args(argv)


def build_server(port: int) -> CorporateServer:
    """Arma el servidor con las tablas reales de DynamoDB."""
    subject = Subject()
    proxy = CorporateDataProxy(CorporateDataTable(), CorporateLogTable(), subject)
    return CorporateServer(proxy, subject, port=port)


def main(argv: Sequence[str] | None = None) -> int:
    """Punto de entrada del servidor; devuelve el código de salida."""
    args = parse_args(argv)
    configure_logging(args.verbose)
    server = build_server(args.port)
    try:
        server.start()
    except ServerError as exc:
        logger.error("%s. ¿Ya hay un servidor en ejecución?", exc)
        return 1
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Cancelado por el usuario")
    finally:
        server.shutdown()
    return 0
