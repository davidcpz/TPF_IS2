# Uso de herramientas de IA

Este archivo registra cómo usé inteligencia artificial durante el trabajo.

## Cómo trabajé

Usé **Claude (Anthropic)** como asistente durante todo el desarrollo. Se trabajo **por etapas y despacio**, con el desarrolo del código
en conjunto y que viniera explicada línea por línea, temas teórico, con una explicación
sencilla. Mi objetivo era entender lo que estaba haciendo, no solo obtener el
código.

**El asistente** propuso corregir la parte que habia propuesto del código de cada etapa, me explicó los conceptos y me
ayudó a interpretar los errores.

**Mi trabajo** en cada etapa fue:

- Armar el entorno: Python, entorno virtual, AWS CLI, credenciales y repositorio en GitHub.
- Incorporar cada módulo al proyecto, ejecutarlo y correr los tests y las
  herramientas de calidad (ruff, black, mypy, pyright, bandit) antes de cada commit.
- Probar el sistema en vivo contra AWS DynamoDB, con hasta tres terminales a la
  vez, y guardar las evidencias.
- Hacer los diagramas UML en draw.io.
- Detectar errores en las pruebas, informarlos y verificar las correcciones.
- Mantener el CHANGELOG y revisar qué archivos subía en cada commit.

## Decisiones propias

- Propuse crear el `.gitignore` antes de empezar, para que el archivo de
  credenciales de AWS nunca llegara al repositorio.
- Propuse ir armando el formato del informe desde el inicio.
- Elegí draw.io para los diagramas UML y los hice a partir de los modelos que
  analizamos.
- Como la tabla `CorporateData` es compartida con otros alumnos, usé un ID propio
  (`TPF-DAVIDCPZ-01`) para probar `set`, sin modificar registros ajenos.
- Antes de cada commit revisé con `git status` y `tree` qué archivos se subían;
  así detecté archivos ubicados en carpetas equivocadas y los reubiqué.

## Errores que encontré en las pruebas

Al probar el sistema encontré fallas en el código propuesto. Las informé, las
analizamos y las corregimos; después volví a probar para confirmar que estaban
resueltas.

| Qué detecté | Por qué pasaba | Cómo se corrigió |
| --- | --- | --- |
| Con `-v`, el servidor llenaba la pantalla de mensajes internos de botocore. | El modo detallado se aplicaba también a las librerías externas. | `-v` se limitó al código propio; boto3 y botocore muestran solo advertencias. |
| El cliente fallaba al usar `-i=ejemplos\list.json`. | PowerShell parte ese argumento en el punto. | Se documentó en el README el uso `-i archivo` (o entre comillas). |
| El ObserverClient no se detenía con Ctrl+C en Windows. | La lectura del socket esperaba sin límite de tiempo. | La espera pasó a hacerse de a 0,5 segundos, para poder atender Ctrl+C. |
| pdoc mostraba advertencias sobre `ClassVar` en las tablas. | Los atributos de la metaclase Singleton aparecían como atributos de cada clase. | Se movieron a variables del módulo `singleton.py`. |

## Conceptos que trabajé


- Los patrones **Singleton** (con metaclase y seguro para hilos), **Observer** y **Proxy**.
- Sockets TCP, hilos y el protocolo de mensajes JSON por línea.
- Entornos virtuales, instalación editable (`pip install -e .`) y estructura `src`.
- Tests con pytest: fixtures, dobles de prueba (tablas en memoria), `parametrize` y cobertura.
- Análisis estático: tipos (mypy, pyright), estilo (PEP 8, PEP 257) y seguridad (bandit).
- Integración continua con GitHub Actions y documentación automática con pdoc.

## Registro de prompts

Resumen de las consultas principales, agrupadas por etapa.

| N.º | Fecha | Etapa | Consulta |
| --- | --- | --- | --- |
| 1 | 2026-10-17 | Inicio | Le pedí ayuda para el TPFI, que leyera las consignas y que las trabajemos en conjunto.|
| 2 | 2026-10-17 | Entorno | Consulté cómo instalar y configurar AWS CLI y las credenciales en Windows. |
| 3 | 2026-10-17 | Seguridad | Pregunté si convenía un `.gitignore` para proteger el archivo de credenciales. |
| 4 | 2026-10-17 | CookieCutter | Pregunté por qué la consigna pide un esqueleto basado en CookieCutter y cómo generarlo. |
| 5 | 2026-10-17 | Git/GitHub | Consulté qué mail configurar en git y cómo verificarlo. |
| 6 | 2026-10-18 | UML | Pedí los modelos de los diagramas para hacerlos yo en draw.io. |
| 7 | 2026-10-18 | Patrones | Pedí implementar paso a paso el Singleton, el acceso a las tablas, el Observer y el Proxy, con sus tests. |
| 8 | 2026-10-18 | Calidad | Consulté cómo resolver los avisos de ruff y configurar VS Code. |
| 9 | 2026-10-18 | Servidor | Pedí avanzar con el servidor TCP y dejar la prueba en vivo para el día siguiente. |
| 10 | 2026-10-19 | Servidor | Consulté por el error al iniciar dos servidores a la vez y por el exceso de mensajes con `-v`. |
| 11 | 2026-10-19 | Organización | Pedí un comando para ver toda la estructura de carpetas y verificar la ubicación de los archivos. |
| 12 | 2026-10-19 | Clientes | Pedí implementar el SingletonClient y consulté por qué un comando fallaba en PowerShell. |
| 13 | 2026-10-19 | Observer | Pedí implementar el ObserverClient e informé que no se detenía con Ctrl+C. |
| 14 | 2026-10-19 | Tests | Pedí los tests de los clientes y consulté el total de tests y la cobertura. |
| 15 | 2026-10-19 | Calidad | Corrí mypy, pyright y bandit y consulté sus resultados. |
| 16 | 2026-10-19 | Documentación y CI | Pedí generar la documentación con pdoc, consulté por sus advertencias y configuré GitHub Actions. |
| 17 | 2026-10-19 | Cierre | Pedí redactar el README y este registro de uso de IA. |
