# RUNBOOK — Cómo usar el proyecto (dev/preprod/prod)

## 0) Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

## 1) Config mínima (.env)

```bash
MOODLE_URL=https://<tu-moodle>
MOODLE_TOKEN=<token>

# Solo si subes a HDFS
STRATIO_URL=https://<tu-stratio>
# opción A: cookies
STRATIO_COOKIE=<cookie>
JSESSIONID=<jsession>
# opción B: login
# STRATIO_USER=<user>
# STRATIO_PASS=<pass>
# STRATIO_TENANT=formacion

HDFS_BASE_PATH=/informes/moodle
AGENT_WORKDIR=/tmp/moodle-reports-agent
```

## 2) Flujo diario recomendado (DEV)

### 2.1 Ingesta sin subida
```bash
python -m batch_agent ingest daily --date 2026-04-23 --skip-upload
```

### 2.2 Validación del snapshot
```bash
python -m batch_agent validate snapshot /tmp/moodle-reports-agent/2026-04-23
```

### 2.3 Comparación entre snapshots
```bash
python -m batch_agent compare snapshots /tmp/moodle-reports-agent/2026-04-22 /tmp/moodle-reports-agent/2026-04-23
```

## 3) Flujo con subida HDFS (PREPROD/PROD)

```bash
python -m batch_agent ingest daily --date 2026-04-23
```

> Si falla por cookies, verifica env o usa login (`STRATIO_USER/STRATIO_PASS`).

## 4) Uso de la skill analítica

### KPIs por partner
```bash
python -m skill kpis /tmp/moodle-reports-agent/2026-04-23
```

### Export CSV
```bash
python -m skill export /tmp/moodle-reports-agent/2026-04-23 /tmp/partner_kpis.csv
```

### Reporting completo (Excel + CSV por tabla)
```bash
python -m skill reporting /tmp/moodle-reports-agent/2026-04-23 \
  --output-excel /tmp/reports_local/informe_formacion.xlsx \
  --output-csv-dir /tmp/reports_local/csv
```

## 5) Uso del MCP server (v1 read-only)

El servidor arranca automáticamente en Claude Code al abrir el proyecto (configurado en `.claude/settings.json`). No es necesario lanzarlo a mano.

Flujo de uso:
```bash
# 1. Genera un snapshot local
python -m batch_agent ingest daily --skip-upload

# 2. Abre el proyecto en Claude Code
# 3. Pregunta directamente: "¿cuántos usuarios tiene pichincha?"
```

Para lanzarlo manualmente (debugging):
```bash
python -m mcp_server.server
```

## 6) Compatibilidad legacy

Si tienes automatizaciones antiguas:
```bash
python -m src.agent.main --date 2026-04-23 --dry-run
```

## 7) Troubleshooting rápido

- **`MOODLE_URL/MOODLE_TOKEN no definidos`**: revisa `.env`.
- **`STRATIO_URL no definido`**: estás intentando subir sin configurar Stratio.
- **snapshot vacío**: ejecuta primero ingesta (`ingest daily`).
- **tool MCP desconocida**: valida nombre en `mcp_server/server.py`.
