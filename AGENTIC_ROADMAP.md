# AGENTIC_ROADMAP

## Skill candidate

### Casos de uso que cubriría
- Validación analítica de snapshots diarios/semanales.
- KPIs por partner, curso, cohorte, versión e idioma.
- Alertas de calidad (caídas bruscas, cohortes vacías, certificaciones atípicas).
- Exportes operativos (CSV/Excel) para auditoría y seguimiento.

### APIs/interfaces necesarias
- `python_core.validation.sanity.run(workdir) -> dict`
- `python_core.validation.sanity.compare_snapshot_counts(base_dir, target_dir, datasets) -> list[dict]`
- Lectura tabular de snapshots (`read_parquet`) y capa de reglas de negocio reutilizable.
- Contrato de salida estable para herramientas externas: JSON + archivos exportados.

## MCP candidate

### Tools MCP v1 (read-only)
- `list_training_partners(workdir)`
- `get_partner_kpis(workdir, partner)`
- `validate_latest_snapshot(workdir)`
- `compare_snapshots(base_dir, target_dir)`

### APIs/interfaces necesarias
- Capa de tools desacoplada en `mcp_server/tools.py` (funciones puras de negocio).
- Dispatcher/server con contrato único de input/output JSON.
- Gestión de errores consistente (tool not found, args inválidos, snapshot inexistente).
- Evolución prevista: auth, rate limiting, auditoría y catálogos de tools versionados.

## Moodle plugin boundary

### Qué debe hacer
- Exponer endpoints webservice bulk y estables para extracción.
- Validar permisos/capabilities para acceso seguro.
- Versionar el contrato de campos devueltos para evitar rupturas en el core.

### Qué NO debe hacer
- No ejecutar lógica de reporting/semántica.
- No contener reglas analíticas de negocio (partners/KPIs/alertas).
- No acoplarse a HDFS, Metabase o flujos de exportes.
- No incluir orchestration batch ni dependencias de infraestructura externa.

## Variante “nuevo repo” recomendada

### `training-reports-core`
- Mover: `python_core/`, `batch_agent/`, tests asociados de core/batch.
- Mantener contrato de librería reutilizable + CLI operacional.

### `training-reports-mcp`
- Mover: `mcp_server/` + parte de `skill/` enfocada a consulta analítica read-only.
- Dependencia explícita de `training-reports-core`.

### `moodle-local-stratiorep`
- Mover: `moodle_plugin/` como repositorio independiente del ciclo Python.
- Publicar versión de plugin + changelog de endpoints para consumidores.
