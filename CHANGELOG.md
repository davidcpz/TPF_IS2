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

## [0.1.0] - 2026-10-17

### Agregado

- Esqueleto del proyecto generado con CookieCutter.
- Configuración de pytest, ruff, black, mypy, pyright y bandit en `pyproject.toml`.
- Archivos `README.md`, `CHANGELOG.md`, `CONTEXT.md`, `LICENSE` (MIT), `VERSION` y `BUILD`.
