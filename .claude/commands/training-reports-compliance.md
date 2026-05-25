# /training-reports-compliance — Informe de cumplimiento de curso interno Stratio

> **Úsalo cuando:** quieras saber qué empleados de Stratio han completado un curso obligatorio (blanqueo de capitales, protección de datos, seguridad, etc.) y quiénes están pendientes.
> Necesita un snapshot previo y el fichero de empleados.

Flujo: localizar snapshot → confirmar parámetros → generar informe → mostrar resultado.

---

## PASO 1 — Localizar el snapshot

Usa la herramienta MCP `get_latest_snapshot`. Si devuelve `status: no_snapshots`, indica que hay que ejecutar `/training-reports-ingest` primero.

---

## PASO 2 — Confirmar parámetros

Pregunta al usuario:
1. **¿Qué curso?** — el patrón de búsqueda en el nombre del curso (ej: `blanqueo`, `protección de datos`, `seguridad`)
2. **¿Fichero de empleados?** — por defecto `/home/jmruiz/Descargas/empleados+mail (1).xlsx`. Confirma si quiere usar ese u otro.
3. **¿Dónde guardar el Excel?** — por defecto `reports/compliance_<curso>_<fecha>.xlsx`

---

## PASO 3 — Generar el informe

Usa la herramienta MCP `run_compliance` con los parámetros confirmados:
- `workdir`: ruta del snapshot
- `course_pattern`: patrón del curso
- `empleados_xlsx`: ruta al fichero de empleados
- `output_excel`: ruta de salida

---

## PASO 4 — Mostrar resultado

Cuando termine, muestra una tabla resumen con:

```
RESUMEN — <nombre del curso>
────────────────────────────────────
Total empleados:     N
Completados:         N  (X%)
Pendientes (inscritos): N
Sin inscribir:       N
────────────────────────────────────
```

Luego muestra el top de roles y departamentos con menor tasa de completado (los que necesitan más atención).

Indica la ruta absoluta del Excel generado con las 6 hojas: resumen, completados, pendientes, sin_inscribir, por_rol, por_departamento.

---

## Notas
- El join entre Moodle y el fichero de empleados se hace por email (normalizado a minúsculas)
- Los empleados sin cuenta en Moodle caen en `sin_inscribir`
- Cada ejecución queda registrada en `AGENT_WORKDIR/log_reports.jsonl`
- El fichero de empleados por defecto: `/home/jmruiz/Descargas/empleados+mail (1).xlsx`
