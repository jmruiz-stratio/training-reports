# REFACTOR_NOTES

## Antes vs Después

### Antes
- Estructura centrada en `src/` con mezcla de responsabilidades:
  - extracción Moodle,
  - serialización/validación,
  - subida HDFS,
  - lógica semántica/reporting,
  - utilidades e imports legacy (`shared.*`) acoplados al runtime local.
- Entry point principal (`src/agent/main.py`) combinaba orquestación, validación, subida y salida por consola en un único flujo.
- Escasa separación entre capa operativa batch, capa analítica y futuras herramientas MCP.

### Después
- Arquitectura modular por capas:
  - `python_core/`: núcleo reutilizable (config, extracción, reglas de dominio, validación técnica/sanity, storage).
  - `batch_agent/`: CLI operacional (`ingest daily`, `validate snapshot`, `compare snapshots`).
  - `skill/`: capacidades analíticas (KPIs/exportes) sobre snapshots.
  - `mcp_server/`: tools read-only de negocio en v1.
  - `moodle_plugin/`: boundary PHP para extracción bulk (sin reporting).
- Compatibilidad preservada con `src/agent/main.py` como shim para argumentos legacy.
- Endpoints de empaquetado unificados (`training-batch`, `training-skill`, `training-mcp`).

## Decisiones importantes
- Se mantiene `src/transform/` en este repo para no romper el pipeline semántico/reporting actual.
- Se centraliza la regla de partner en `python_core.domain.rules` para evitar deriva funcional.
- Se añade paquete `shared/` de compatibilidad para endurecer imports legacy sin depender de hacks de `sys.path`.
- MCP v1 se limita a lectura y herramientas de negocio de alto nivel (no wrappers de tablas crudas).

## Riesgos pendientes
- MCP aún usa dispatcher mínimo; falta formalizar contrato sobre SDK MCP y esquema de auth/audit.
- Las funciones custom de Moodle dependen del despliegue correcto del plugin (`local_stratiorep`).
- La capa `python_core.extraction` conserva fallbacks complejos (útil hoy, pero con deuda de mantenibilidad).
- Aún conviven módulos nuevos con legado en `src/`; requiere plan de deprecación gradual.

## Siguientes pasos
1. Formalizar interfaces tipadas para datasets (pydantic/dataclasses por snapshot).
2. Añadir tests de integración de `batch_agent` con fixtures Parquet y validación de contratos.
3. Migrar `skill` a análisis multiperspectiva (partner/curso/cohorte/versión/certificación).
4. Implementar MCP server con transporte y registro de tools estándar.
5. Definir política de extracción a nuevos repos (core/mcp/plugin) con versionado coordinado.


## Packaging hardening applied
- Se añadieron `__main__.py` para `batch_agent`, `skill` y `mcp_server` para ejecución consistente con `python -m paquete`.
- Se corrigió la semántica de `--skip-upload`/`--dry-run` en `batch_agent.cli` y en `runner` para evitar omitir subidas por defecto.
- Se movió `load_env` a `python_core.utils` y se añadió `python_core.auth` para centralizar cookies Rocket.
