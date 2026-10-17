"""Tests básicos del paquete."""

from pathlib import Path

from corporate_data_server import __version__


def test_version_coincide_con_archivo_version() -> None:
    """La versión del paquete es la misma que la del archivo VERSION."""
    archivo_version = Path(__file__).resolve().parents[1] / "VERSION"
    assert __version__ == archivo_version.read_text(encoding="utf-8").strip()
