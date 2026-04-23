# Training Reports — Estado actual del proyecto (v4)

Este documento resume la arquitectura vigente tras el refactor modular.

> El detalle funcional histórico completo (consultas, reglas y contexto extenso) se conserva en `docs/CLAUDE_LEGACY_DETAILS.md` para no perder conocimiento.

## 1) Objetivo

Automatizar la extracción de datos de formación desde Moodle, validar snapshots y habilitar consumo analítico en capas separadas:

- **Plugin Moodle** (boundary de extracción)
- **Python Core** (lógica reutilizable)
- **Batch Agent** (operación diaria)
- **Skill** (KPIs/exportes)
- **MCP Server** (tools read-only de negocio)

## 2) Arquitectura vigente

```text
moodle_plugin/      -> Endpoints Moodle bulk (sin reporting)
python_core/        -> Config, auth, extracción, validación, storage
batch_agent/        -> CLI operativa (ingest/validate/compare)
skill/              -> CLI analítica (kpis/export)
mcp_server/         -> Dispatcher read-only v1 por tools
src/transform/      -> SQL semántica + reporting (se mantiene)
src/agent/main.py   -> shim de compatibilidad para flujo legacy
```

## 3) Responsabilidades por capa

### moodle_plugin/
- Solo extracción webservice estable y segura.
- No debe incluir lógica de KPIs/reporting/orquestación.

### python_core/
- Núcleo reutilizable:
  - `config.py` (settings + datasets)
  - `auth.py` (cookies/login Rocket)
  - `extraction.py` (orquestación de datasets Moodle)
  - `storage/` (parquet + hdfs adapter)
  - `validation/` (técnica + sanity)

### batch_agent/
- Operación diaria:
  - `ingest daily`
  - `validate snapshot`
  - `compare snapshots`

### skill/
- Analítica local sobre snapshots:
  - KPIs por partner
  - export CSV base
  - generación completa de reporting (Excel + CSV por tablas)

### mcp_server/
- Capa read-only v1 de tools de alto nivel:
  - `list_training_partners`
  - `get_partner_kpis`
  - `validate_latest_snapshot`
  - `compare_snapshots`

## 4) Entrypoints activos

- `python -m batch_agent ...`
- `python -m skill ...`
- `python -m mcp_server.server`
- Legacy compatible: `python -m src.agent.main --date YYYY-MM-DD [--dry-run|--skip-upload]`

También existen scripts de paquete:
- `training-batch`
- `training-skill`
- `training-mcp`

## 5) Variables de entorno mínimas

### Para extracción Moodle
- `MOODLE_URL`
- `MOODLE_TOKEN`

### Para subida HDFS (si no se usa --skip-upload)
- `STRATIO_URL`
- cookies (`STRATIO_COOKIE` + `JSESSIONID`) **o**
- login (`STRATIO_USER`, `STRATIO_PASS`, opcional `STRATIO_TENANT`)

### Opcionales
- `HDFS_BASE_PATH` (default `/informes/moodle`)
- `AGENT_WORKDIR` (default `/tmp/moodle-reports-agent`)

## 6) Flujo operativo recomendado

1. Ejecutar ingesta diaria en modo seguro local (`--skip-upload`).
2. Validar snapshot resultante (`validate snapshot`).
3. Comparar contra snapshot anterior (`compare snapshots`).
4. Ejecutar skill de KPIs/exportes (incluido reporting completo Excel+CSV) si hace falta revisión de negocio.
5. Ejecutar con subida real sin `--skip-upload` solo cuando credenciales/entorno estén validados.

## 7) Estado de migración

- `src/transform/` permanece en este repo para continuidad.
- `src/agent/main.py` se mantiene como compatibilidad temporal.
- Objetivo futuro: separar repos en:
  - `training-reports-core`
  - `training-reports-mcp`
  - `moodle-local-stratiorep`

## 8) Documentos clave

- `README.md` → overview + comandos
- `RUNBOOK.md` → guía práctica de uso diario
- `REFACTOR_NOTES.md` → decisiones/riesgos/siguientes pasos
- `AGENTIC_ROADMAP.md` → boundary skill/MCP/plugin
