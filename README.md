# Training Reports — Moodle → Stratio → Metabase

Automatización de informes de formación: extracción diaria desde Moodle, carga en HDFS y generación de dashboards en Metabase.

## Estructura

| Directorio | Qué hace |
|---|---|
| `moodle_plugin/` | Plugin PHP `local_stratiorep` — 7 funciones de extracción bulk |
| `python_core/` | Núcleo reutilizable: extracción, validación, storage HDFS, auth |
| `batch_agent/` | CLI operativa: ingesta diaria, validación y comparación de snapshots |
| `skill/` | CLI analítica: KPIs, exportes CSV/Excel por partner |
| `mcp_server/` | MCP server (Claude Code) — 4 tools read-only de negocio |
| `src/transform/` | SQL Spark para capas semántica y reporting (ejecución única en Stratio) |
| `src/local_validate.py` | Validación local semántica + reporting en DuckDB → Excel |
| `src/data/` | `partners_meta.csv` — metadatos de negocio por partner |

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .[dev]
cp .env.example .env   # rellenar MOODLE_URL, MOODLE_TOKEN, STRATIO_*
```

## Comandos principales

```bash
# Ingesta diaria (sin subir a HDFS)
training-batch ingest daily --skip-upload

# Ingesta completa (extrae + valida + sube a HDFS)
training-batch ingest daily

# Validar snapshot
training-batch validate snapshot /tmp/moodle-reports-agent/2026-04-23

# Comparar dos días
training-batch compare snapshots /tmp/.../2026-04-22 /tmp/.../2026-04-23

# Reporting local completo (Excel + CSV)
training-skill reporting /tmp/moodle-reports-agent/2026-04-23

# Reporting solo para un partner
training-skill reporting /tmp/moodle-reports-agent/2026-04-23 --partner pichincha
```

## Documentación

- `CLAUDE.md` — contexto maestro completo (arquitectura, reglas de negocio, SQL, decisiones, roadmap)
- `RUNBOOK.md` — guía operativa paso a paso (dev/preprod/prod)

## Compatibilidad legacy

```bash
python -m src.agent.main --date 2026-04-23 --skip-upload
```
