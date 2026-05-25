# /training-reports-ingest — Descarga diaria de datos Moodle

> **Úsalo cuando:** quieras descargar los datos del día (o de una fecha concreta) desde Moodle.
> Extrae los 10 datasets, los guarda como Parquet en `/tmp/moodle-reports-agent/<fecha>/` y valida que la descarga fue correcta.
> Si el token está caducado → empieza por `/training-reports-validate` para diagnosticar.

Flujo: verificar credenciales → lanzar ingesta → confirmar resultado.

---

## PASO 1 — Verificar credenciales

Usa la herramienta MCP `check_auth`. Si devuelve `status: error`, para aquí e indica al usuario que debe actualizar `MOODLE_TOKEN` en el fichero `.env` del proyecto.

Si devuelve `status: ok`, muestra el sitio y usuario y continúa.

---

## PASO 2 — Lanzar ingesta

Usa la herramienta MCP `run_ingest` con el parámetro `date_str` vacío para la fecha de hoy, o con formato `YYYY-MM-DD` si el usuario especifica una fecha concreta.

La ingesta puede tardar entre 1 y 5 minutos según el volumen. Muestra un mensaje de espera.

---

## PASO 3 — Confirmar resultado

Cuando `run_ingest` termine, muestra una tabla resumen con:
- Ruta del snapshot generado
- Datasets descargados (con checksum ok/ko)
- KPIs básicos: partners, usuarios, cohortes, certificaciones

Si algún dataset tiene 0 filas o checksum fallido, indícalo claramente y sugiere ejecutar `/training-reports-validate` para más detalle.

---

## Notas
- Los Parquet quedan en `AGENT_WORKDIR/<fecha>/` (por defecto `/tmp/moodle-reports-agent/<fecha>/`)
- Cada ejecución queda registrada en `AGENT_WORKDIR/log_reports.jsonl`
- Para generar el informe Excel después: `/training-reports-export`
