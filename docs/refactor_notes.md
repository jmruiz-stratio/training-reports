# Refactor notes

## Supuestos
- Se prioriza continuidad operativa sobre rediseño total de SQL/infra.
- Se conserva `src/transform/` como capa semántica/reporting vigente.
- El servidor MCP se entrega en modo read-only v1 con dispatcher mínimo.

## Dudas abiertas
- Definir contrato final MCP (SDK objetivo, transporte y auth).
- Decidir si `src/` se depreca por completo en siguiente iteración.
- Alinear naming de datasets custom Moodle con governance de APIs.

## Riesgos detectados y mitigaciones
- **Acoplamiento extraction↔fallbacks**: extraído a `python_core.extraction` para centralizar.
- **Duplicidad de regla partner**: consolidada en `python_core.domain.rules` y smoke tests.
- **Entrypoints dispersos**: normalizados con CLIs explícitas (`batch_agent`, `skill`).
