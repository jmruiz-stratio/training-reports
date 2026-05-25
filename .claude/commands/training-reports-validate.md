# /training-reports-validate — Diagnostica el estado del snapshot y las credenciales

> **Úsalo cuando:** algo falla, quieras verificar que el token funciona, o comprobar que un snapshot está íntegro antes de generar informes.

Flujo: verificar credenciales → inspeccionar snapshot → mostrar diagnóstico.

---

## PASO 1 — Verificar token Moodle

Usa la herramienta MCP `check_auth`.

- Si `status: ok` → muestra sitio y usuario. Continúa.
- Si `status: error` → **para aquí**. Indica al usuario:
  ```
  ⚠ Token caducado o inválido.
  Actualiza MOODLE_TOKEN en .env con el token vigente.
  Puedes copiarlo de training-exams-agent/.env si ese proyecto funciona.
  ```

---

## PASO 2 — Inspeccionar snapshot

Usa la herramienta MCP `get_latest_snapshot`.

Muestra tabla con:
- Fecha del snapshot
- Datasets presentes y su tamaño en KB
- Datasets ausentes (si falta alguno de los 10 esperados)

Los 10 datasets esperados son:
`users, courses, cohorts, cohort_members, user_courses, user_grades, course_completions, cohort_members_ext, attendance_sessions, enrol_cohort_course`

---

## PASO 3 — Validar KPIs

Usa la herramienta MCP `validate_latest_snapshot` con la ruta del snapshot.

Muestra los KPIs resultantes y señala cualquier valor anómalo:
- Usuarios < 100 → sospechoso
- Partners = 0 → error de extracción
- Certificaciones > usuarios activos → inconsistencia

---

## PASO 4 — Diagnóstico final

Resume el estado en una de estas categorías:
- ✅ **Todo correcto** — snapshot válido, listo para generar informes
- ⚠ **Warnings** — snapshot parcial, algunos datasets con menos filas de lo esperado
- ❌ **Error** — token caducado o snapshot corrupto, necesita acción

Sugiere el siguiente paso según el diagnóstico.
