# /training-reports-export — Genera el Excel de reporting de formación

> **Úsalo cuando:** quieras generar el informe Excel completo (6 hojas) con todos los KPIs de partners, certificaciones, evolución mensual y alertas.
> Necesita un snapshot previo. Si no hay ninguno → empieza con `/training-reports-ingest`.

Flujo: localizar snapshot → generar Excel → mostrar resultado.

---

## PASO 1 — Localizar el snapshot

Usa la herramienta MCP `get_latest_snapshot`. Si devuelve `status: no_snapshots`, para aquí e indica al usuario que debe ejecutar `/training-reports-ingest` primero.

Si hay snapshot, muestra la fecha y los datasets disponibles y pide confirmación para continuar (o pregunta si quiere usar ese snapshot o uno de fecha distinta).

---

## PASO 2 — Generar el Excel

Ejecuta en terminal:

```bash
training-skill reporting <workdir> \
  --output-excel reports/informe_formacion_<fecha>.xlsx \
  --practices reports/sesiones_practicas.csv
```

Sustituye `<workdir>` por la ruta del snapshot y `<fecha>` por la fecha del snapshot.

Si el usuario quiere filtrar por un partner concreto, añade `--partner <nombre_partner>`.

---

## PASO 3 — Mostrar resultado

Cuando termine, muestra:
- Ruta absoluta del Excel generado
- Hojas incluidas con número de filas cada una
- Si hay alertas (`r_alertas`): lista los partners sin actividad >30 días

Pregunta si quiere abrir el fichero o compartirlo.

---

## Notas
- El Excel incluye: resumen_ejecutivo, resumen_partner, evolucion_mensual, partner_categoria, partner_version, detalle_certificados, alertas
- Si existe `reports/sesiones_practicas.csv` se añaden automáticamente las hojas de prácticas
- Para un informe de un curso interno concreto: `/training-reports-compliance`
