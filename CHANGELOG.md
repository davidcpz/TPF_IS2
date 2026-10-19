# Changelog

Todos los cambios importantes del proyecto se registran en este archivo.

El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/)
y el proyecto usa [Versionado Semántico](https://semver.org/lang/es/).

## [Sin publicar]

### Agregado

- Diagramas UML de actividad (proxy) y de estados (observer) en `docs/uml`, hechos con draw.io.
- Patrón Singleton (`SingletonMeta`) y clases de acceso a las tablas `CorporateData` y `CorporateLog`, con tests.
- Protocolo de mensajes JSON por línea, patrón Observer (`Subject`) y patrón Proxy (`CorporateDataProxy`), con tests.
- Servidor TCP `singletonproxyobserver.py` con un hilo por cliente, argumentos `-p` y `-v`, y tests con sockets reales.
- `singletonclient.py`: cliente que envía get, set o list desde un archivo JSON
  (`-i`), muestra la respuesta y la guarda opcionalmente (`-o`).
- `observerclient.py`: cliente suscripto que recibe cada actualización; si el
  servidor se cae reintenta cada 30 segundos (`-r`) y se vuelve a suscribir.
- `cli.py`: validación de argumentos compartida (formato `-p=8080`) y logging
  con `-v` solo para el código propio.
- `ejemplos/`: archivos de pedido de ejemplo (get, list, set).
- Tests de los clientes y de `cli.py` (servidor de prueba con tablas en memoria,
  casos de servidor caído y reconexión): 131 tests, cobertura 97%.
- Integración continua con GitHub Actions (`.github/workflows/ci.yml`): en cada
  push corre ruff, black, mypy, pyright, bandit, pytest con cobertura y genera
  la documentación con pdoc.
- Documentación de la API generada con pdoc (`pdoc corporate_data_server -o docs/api`).

### Corregido

- ObserverClient: Ctrl+C no cortaba el programa en Windows mientras esperaba
  notificaciones; ahora espera de a 0,5 segundos.
- Servidor: `-v` mostraba los mensajes internos de boto3/botocore.
- Singleton: los atributos internos de la metaclase aparecían como atributos de
  cada clase y generaban advertencias en pdoc; ahora se guardan a nivel de módulo.

## [0.1.0] - 2026-10-17

### Agregado

- Esqueleto del proyecto generado con CookieCutter.
- Configuración de pytest, ruff, black, mypy, pyright y bandit en `pyproject.toml`.
- Archivos `README.md`, `CHANGELOG.md`, `CONTEXT.md`, `LICENSE` (MIT), `VERSION` y `BUILD`.

