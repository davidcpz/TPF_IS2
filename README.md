# Corporate Data Server

Servidor de datos corporativos con patrones Singleton, Observer y Proxy sobre AWS DynamoDB (TPFI IS2 UADER-FCyT).

Trabajo Práctico Final Integrador de **Ingeniería de Software II** — UADER, Facultad de Ciencia y Tecnología.

## Componentes

| Programa | Función |
| --- | --- |
| `singletonproxyobserver.py` | Servidor TCP (puerto 8080) que atiende `get`, `set`, `list` y `subscribe` |
| `singletonclient.py` | Cliente que envía un `input.json` al servidor y muestra la respuesta |
| `observerclient.py` | Cliente que se suscribe y recibe los cambios en tiempo real |

## Requisitos

- Python 3.11 o superior
- Credenciales de AWS configuradas con `aws configure` (nunca dentro del repositorio)

## Instalación

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1        # Windows PowerShell
source .venv/bin/activate         # Linux / Mac
pip install -r requirements.txt
```

## Uso

_Se completa a medida que se implementan los programas._

## Calidad

```bash
pytest --cov
ruff check .
black --check .
mypy
pyright
bandit -c pyproject.toml -r src
```

## Licencia

MIT — ver [LICENSE](LICENSE).
