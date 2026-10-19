# Corporate Data Server

[![CI](https://github.com/davidcpz/TPF_IS2/actions/workflows/ci.yml/badge.svg)](https://github.com/davidcpz/TPF_IS2/actions/workflows/ci.yml)

Servidor de datos corporativos con patrones Singleton, Observer y Proxy sobre AWS DynamoDB (TPFI IS2 UADER-FCyT).

Trabajo Práctico Final Integrador de **Ingeniería de Software II** — UADER, Facultad de Ciencia y Tecnología.

## Componentes

| Programa | Función |
| --- | --- |
| `singletonproxyobserver.py` | Servidor TCP (puerto 8080) que atiende `get`, `set`, `list` y `subscribe` |
| `singletonclient.py` | Cliente que envía un `input.json` al servidor y muestra la respuesta |
| `observerclient.py` | Cliente que se suscribe y recibe los cambios en tiempo real |

## Patrones de diseño

| Patrón | Dónde | Para qué |
| --- | --- | --- |
| **Singleton** | `singleton.py` (`SingletonMeta`) | Una única instancia de acceso a cada tabla (`CorporateData`, `CorporateLog`), segura para hilos |
| **Proxy** | `proxy.py` (`CorporateDataProxy`) | Valida cada pedido y registra la auditoría en `CorporateLog` **antes** de acceder a `CorporateData` |
| **Observer** | `observer.py` (`Subject`) | Avisa a todos los clientes suscriptos cada vez que un `set` modifica un registro |

Los diagramas UML (actividad del proxy y estados del observer) están en [`docs/uml`](docs/uml).

## Requisitos

- Python 3.11 o superior
- Credenciales de AWS configuradas con `aws configure` (nunca dentro del repositorio)
- Acceso a las tablas DynamoDB `CorporateData` y `CorporateLog`

## Instalación

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1        # Windows PowerShell
source .venv/bin/activate         # Linux / Mac
pip install -r requirements.txt
pip install -e .
```

`pip install -e .` instala el paquete `corporate_data_server` en modo editable,
para que los programas de la raíz puedan importarlo.

## Uso

### Servidor

```bash
python singletonproxyobserver.py {-p=puerto} {-v}
```

| Argumento | Descripción | Por defecto |
| --- | --- | --- |
| `-p` | Puerto TCP donde escucha | `8080` |
| `-v` | Modo detallado: muestra cada conexión, pedido y respuesta | desactivado |

Se detiene con **Ctrl+C**. Si el puerto está ocupado, informa el error y termina con código 1.

### SingletonClient

```bash
python singletonclient.py -i input.json {-o=output.json} {-s=servidor} {-p=puerto} {-v}
```

| Argumento | Descripción | Por defecto |
| --- | --- | --- |
| `-i` | Archivo JSON con el pedido (**obligatorio**) | — |
| `-o` | Archivo donde guardar la respuesta | solo se muestra en pantalla |
| `-s` | Servidor | `localhost` |
| `-p` | Puerto | `8080` |
| `-v` | Modo detallado | desactivado |

Si el pedido no trae `UUID`, se completa con el identificador de la CPU (`uuid.getnode()`).

Ejemplos de pedidos (carpeta [`ejemplos`](ejemplos)):

```json
{"ACTION": "list"}
```

```json
{"ID": "UADER-FCyT-IS2", "ACTION": "get"}
```

```json
{"ID": "TPF-DAVIDCPZ-01", "ACTION": "set", "sede": "FCyT", "telefono": "03442 11-1111"}
```

> **Nota para Windows PowerShell:** escribir `-i ejemplos\list.json` (con espacio).
> La forma `-i=ejemplos\list.json` sin comillas falla porque PowerShell parte el
> argumento en el punto; si se quiere usar el `=`, hay que ponerlo entre comillas:
> `"-i=ejemplos\list.json"`.

> **La tabla `CorporateData` es compartida:** para probar `set`, usar un `ID` propio
> y no modificar registros de otras personas.

Códigos de salida: `0` respuesta correcta; `1` error (servidor caído, archivo
inválido o respuesta con `Error`); `2` argumentos mal escritos.

### ObserverClient

```bash
python observerclient.py {-s=servidor} {-p=puerto} {-o=output.json} {-r=segundos} {-v}
```

| Argumento | Descripción | Por defecto |
| --- | --- | --- |
| `-s` | Servidor | `localhost` |
| `-p` | Puerto | `8080` |
| `-o` | Archivo donde guardar la última notificación | solo se muestra en pantalla |
| `-r` | Segundos entre reintentos si el servidor no está | `30` |
| `-v` | Modo detallado | desactivado |

Se suscribe y muestra cada registro modificado por un `set`. Si la conexión se
corta o el servidor no está disponible, reintenta cada `-r` segundos y, al
reconectar, vuelve a enviar la suscripción. Se detiene con **Ctrl+C**.

### Prueba completa (tres terminales)

```bash
python singletonproxyobserver.py -v               # terminal 1: servidor
python observerclient.py -v                       # terminal 2: observador
python singletonclient.py -i ejemplos\set.json    # terminal 3: cambio de datos
```

La notificación del `set` aparece automáticamente en la terminal 2.

## Protocolo

Mensajes **JSON por línea** sobre TCP, en UTF-8: cada mensaje es un objeto JSON
terminado en `\n`.

| Acción | Pedido | Respuesta |
| --- | --- | --- |
| `get` | `UUID`, `ID` | El registro, o `{"Error": ...}` si no existe |
| `set` | `UUID`, `ID` y los campos a modificar | El registro actualizado (y se notifica a los suscriptos) |
| `list` | `UUID` | Lista con todos los registros |
| `subscribe` | `UUID` | `{"status": "subscribed"}`; luego, una línea por cada cambio |

Cada pedido válido queda registrado en `CorporateLog` con el UUID del cliente,
la sesión, la acción y la fecha y hora.

## Estructura

```
corporate_data_server/
├── singletonproxyobserver.py   # servidor
├── singletonclient.py          # cliente de pedidos
├── observerclient.py           # cliente suscripto
├── src/corporate_data_server/  # paquete con el código
├── tests/                      # tests automáticos (pytest)
├── ejemplos/                   # pedidos JSON de ejemplo
├── docs/uml/                   # diagramas UML (draw.io)
└── .github/workflows/ci.yml    # integración continua
```

## Calidad

```bash
pytest --cov=corporate_data_server --cov-report=term-missing
ruff check .
black --check .
mypy
pyright
bandit -c pyproject.toml -r src
```

- **131 tests** automáticos, con cobertura del **97%** (mínimo exigido: 85%).
- Los tests no usan AWS: trabajan con tablas en memoria y servidores locales,
  incluidos los casos de servidor caído y reconexión.
- Estilo PEP 8 (ruff, black) y docstrings PEP 257.

## Documentación

```bash
pdoc corporate_data_server -o docs/api
```

Genera la documentación de la API a partir de los docstrings en `docs/api/index.html`.

## Integración continua

En cada push a `main`, GitHub Actions instala el proyecto en una máquina limpia y
corre ruff, black, mypy, pyright, bandit y pytest con cobertura, y genera la
documentación con pdoc (disponible como *artifact* de cada ejecución).

## Uso de IA

Los prompts utilizados durante el desarrollo están registrados en [`CONTEXT.md`](CONTEXT.md).

## Licencia

MIT — ver [LICENSE](LICENSE).
