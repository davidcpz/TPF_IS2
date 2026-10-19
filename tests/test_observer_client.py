"""Tests del cliente ObserverClient: suscripción, notificaciones y reintentos."""

from __future__ import annotations

import json
import socket
import threading
from collections.abc import Iterator
from pathlib import Path

import pytest

from conftest import (
    REGISTRO_INICIAL,
    ServidorDePrueba,
    esperar,
    puerto_libre,
)
from corporate_data_server import observer_client as modulo
from corporate_data_server.observer_client import (
    DEFAULT_RETRY_SECONDS,
    ObserverClient,
    SubscriptionError,
    main,
    parse_args,
)
from corporate_data_server.protocol import encode
from corporate_data_server.singleton_client import send_request
from corporate_data_server.tables import CorporateDataTable, CorporateLogTable


def correr_en_hilo(cliente: ObserverClient) -> threading.Thread:
    """Arranca el cliente en un hilo aparte."""
    hilo = threading.Thread(target=cliente.run, daemon=True)
    hilo.start()
    return hilo


def hacer_set(servidor: ServidorDePrueba, **campos: str) -> None:
    """Modifica el registro inicial como lo haría singletonclient."""
    pedido = {"UUID": "CPU-1", "ACTION": "set", "ID": REGISTRO_INICIAL["id"]}
    send_request({**pedido, **campos}, "127.0.0.1", servidor.port)


class ServidorFalso:
    """Servidor mínimo que responde líneas fijas y corta la conexión."""

    def __init__(self, lineas: list[bytes]) -> None:
        """Abre un puerto libre y atiende una sola conexión en un hilo."""
        self.lineas = lineas
        self.sock = socket.socket()
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen()
        self.port = int(self.sock.getsockname()[1])
        threading.Thread(target=self._atender, daemon=True).start()

    def _atender(self) -> None:
        conn, _ = self.sock.accept()
        with conn:
            conn.makefile("rb").readline()
            for linea in self.lineas:
                conn.sendall(linea)

    def cerrar(self) -> None:
        """Cierra el puerto."""
        self.sock.close()


@pytest.fixture
def servidor_falso() -> Iterator[list[ServidorFalso]]:
    """Lista donde cada test agrega sus servidores falsos; se cierran al final."""
    creados: list[ServidorFalso] = []
    yield creados
    for srv in creados:
        srv.cerrar()


# ---------- Notificaciones ----------


def test_recibe_y_guarda_cada_notificacion(
    servidor: ServidorDePrueba, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Cada set llega al observador, se muestra y se guarda en el archivo."""
    salida = tmp_path / "output.json"
    cliente = ObserverClient("127.0.0.1", servidor.port, salida, retry_seconds=0.05)
    hilo = correr_en_hilo(cliente)
    assert esperar(lambda: servidor.sujeto.count == 1)

    hacer_set(servidor, telefono="111")
    assert esperar(lambda: cliente.received == 1)
    hacer_set(servidor, telefono="222")
    assert esperar(lambda: cliente.received == 2)

    assert json.loads(salida.read_text(encoding="utf-8"))["telefono"] == "222"
    assert '"telefono": "111"' in capsys.readouterr().out

    cliente.stop()
    servidor.detener()
    hilo.join(timeout=5)
    assert not hilo.is_alive()


def test_se_suscribe_con_el_uuid_de_la_cpu(servidor: ServidorDePrueba) -> None:
    """La suscripción queda auditada con el UUID del cliente."""
    cliente = ObserverClient("127.0.0.1", servidor.port, client_uuid="CPU-OBS")
    hilo = correr_en_hilo(cliente)
    assert esperar(lambda: servidor.sujeto.count == 1)
    (log,) = servidor.log.items.values()
    assert log["action"] == "subscribe"
    assert log["CPUid"] == "CPU-OBS"
    cliente.stop()
    servidor.detener()
    hilo.join(timeout=5)


# ---------- Servidor caído y reintentos ----------


def test_servidor_caido_reintenta_y_termina() -> None:
    """Sin servidor, el cliente reintenta las veces indicadas sin romperse."""
    cliente = ObserverClient("127.0.0.1", puerto_libre(), retry_seconds=0.01)
    cliente.run(max_connections=3)
    assert cliente.received == 0


def test_se_reconecta_cuando_el_servidor_vuelve() -> None:
    """Si el servidor aparece después, el cliente se conecta y se suscribe."""
    CorporateDataTable.reset_instance()
    CorporateLogTable.reset_instance()
    puerto = puerto_libre()
    cliente = ObserverClient("127.0.0.1", puerto, retry_seconds=0.05)
    hilo = correr_en_hilo(cliente)

    srv = ServidorDePrueba(port=puerto)
    srv.iniciar()
    try:
        assert esperar(lambda: srv.sujeto.count == 1)
    finally:
        cliente.stop()
        srv.detener()
        hilo.join(timeout=5)
        CorporateDataTable.reset_instance()
        CorporateLogTable.reset_instance()


def test_si_el_servidor_corta_vuelve_a_suscribirse(servidor: ServidorDePrueba) -> None:
    """Tras un corte, el cliente reconecta y envía de nuevo la suscripción."""
    cliente = ObserverClient("127.0.0.1", servidor.port, retry_seconds=0.05)
    hilo = correr_en_hilo(cliente)
    assert esperar(lambda: servidor.sujeto.count == 1)

    servidor.sujeto.close_all()  # simula una caída de la conexión
    assert esperar(lambda: len(servidor.log.items) == 2)
    assert esperar(lambda: servidor.sujeto.count == 1)

    cliente.stop()
    servidor.detener()
    hilo.join(timeout=5)


# ---------- Respuestas inesperadas ----------


def test_suscripcion_rechazada(servidor_falso: list[ServidorFalso]) -> None:
    """Si el servidor responde Error a la suscripción, se lanza SubscriptionError."""
    falso = ServidorFalso([encode({"Error": "no autorizado"})])
    servidor_falso.append(falso)
    with pytest.raises(SubscriptionError):
        ObserverClient("127.0.0.1", falso.port).run(max_connections=1)


def test_conexion_cortada_sin_respuesta(servidor_falso: list[ServidorFalso]) -> None:
    """Si el servidor corta sin responder, se cuenta como un intento más."""
    falso = ServidorFalso([])
    servidor_falso.append(falso)
    cliente = ObserverClient("127.0.0.1", falso.port, retry_seconds=0.01)
    cliente.run(max_connections=1)
    assert cliente.received == 0


def test_mensaje_invalido_se_ignora(servidor_falso: list[ServidorFalso]) -> None:
    """Una línea que no es JSON se ignora y se siguen procesando las demás."""
    falso = ServidorFalso(
        [
            encode({"status": "subscribed", "UUID": "X"}),
            b"esto no es json\n",
            encode({"id": "A"}),
        ]
    )
    servidor_falso.append(falso)
    cliente = ObserverClient("127.0.0.1", falso.port)
    cliente.run(max_connections=1)
    assert cliente.received == 1


# ---------- Programa completo ----------


def test_argumentos_por_defecto() -> None:
    """Sin argumentos: localhost:8080, reintento cada 30 segundos."""
    args = parse_args([])
    assert (args.server, args.port, args.retry) == ("localhost", 8080, 30.0)
    assert DEFAULT_RETRY_SECONDS == 30.0


@pytest.mark.parametrize("argv", [["-p=abc"], ["-r=0"], ["-s="], ["-x"]])
def test_argumentos_malformados(argv: list[str]) -> None:
    """Argumentos inválidos terminan con código 2."""
    with pytest.raises(SystemExit) as salida:
        parse_args(argv)
    assert salida.value.code == 2


def test_main_termina_con_ctrl_c(monkeypatch: pytest.MonkeyPatch) -> None:
    """Main devuelve 0 cuando se cancela con Ctrl+C."""

    def cancelar(self: ObserverClient) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(modulo.ObserverClient, "run", cancelar)
    assert main(["-o=salida.json", "-v"]) == 0


def test_main_suscripcion_rechazada(servidor_falso: list[ServidorFalso]) -> None:
    """Main devuelve 1 si el servidor rechaza la suscripción."""
    falso = ServidorFalso([encode({"Error": "no autorizado"})])
    servidor_falso.append(falso)
    assert main(["-s=127.0.0.1", f"-p={falso.port}"]) == 1
