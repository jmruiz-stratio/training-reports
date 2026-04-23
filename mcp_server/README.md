# mcp_server

Servidor MCP read-only v1 con tools de alto nivel:
- `list_training_partners`
- `get_partner_kpis`
- `validate_latest_snapshot`
- `compare_snapshots`

Implementa el protocolo MCP estándar con FastMCP. Configurado en `.claude/settings.json` — arranca automáticamente en Claude Code al abrir el proyecto. Solo funciona con Claude Code (CLI/VSCode), no con claude.ai web. Lee Parquet locales — no descarga de HDFS.
