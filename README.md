# Training Reports — Clean Product/Agent Architecture

Este repositorio se ha refactorizado para separar responsabilidades y preparar una evolución a producto + agentes.

## Estructura

- `moodle_plugin/`: plugin Moodle mínimo y seguro (solo extracción bulk estable).
- `python_core/`: librería reutilizable con cliente Moodle, extracción RAW, validación y adaptadores de storage.
- `batch_agent/`: CLI de ingesta diaria y validación/comparación de snapshots.
- `skill/`: capa analítica (KPIs y exportes CSV/Excel).
- `mcp_server/`: capa MCP read-only v1 con tools de negocio de alto nivel.
- `src/transform/`: SQL semántico y reporting (se mantiene).
- `REFACTOR_NOTES.md`: supuestos, decisiones, riesgos y siguientes pasos.
- `AGENTIC_ROADMAP.md`: hoja de ruta por capas (skill, MCP, plugin).
- `RUNBOOK.md`: guía operativa paso a paso (dev/preprod/prod).
- `CLAUDE.md`: estado técnico actual del proyecto y límites de cada capa.

## Comandos principales

```bash
python -m batch_agent ingest daily --date 2026-04-22 --skip-upload
python -m batch_agent validate snapshot /tmp/moodle-reports-agent/2026-04-22
python -m batch_agent compare snapshots /tmp/snap-a /tmp/snap-b
python -m skill kpis /tmp/moodle-reports-agent/2026-04-22
python -m mcp_server.server
```

## Migration guide

### Qué se queda en este repo
- Plugin Moodle (`moodle_plugin/`) y SQL de transformaciones (`src/transform/`).
- `python_core/` como núcleo compartido por batch, skill y MCP.

### Qué puede separarse a repos nuevos
- `mcp_server/` (producto de consulta operativo independiente).
- `skill/` (skill analítica portable, versionable y desplegable aparte).

### Candidatas a skill
- Validación analítica de snapshots.
- KPIs por partner/curso/cohorte.
- Exportes CSV/Excel para auditoría.

### Candidatas a MCP
- Tools de consulta read-only: partners, KPIs, estado de formación, comparación de snapshots.
- Orquestación de consultas de negocio (no wrappers crudos de tablas).

### Qué debe seguir siendo plugin Moodle
- Endpoints webservice bulk de lectura.
- Declaración de capabilities/permisos y versionado de APIs.
- Cero lógica de reporting o negocio en PHP.

## Compatibilidad

- Se mantiene `src/agent/main.py` como entrypoint de compatibilidad, redirigido al nuevo CLI de `batch_agent`.
