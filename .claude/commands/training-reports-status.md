# /training-reports-status — Estado rápido del sistema

> **Úsalo cuando:** quieras saber de un vistazo si todo está en orden: token, snapshot y últimas acciones.

Flujo: verificar token → snapshot reciente → últimas acciones del log.

---

## PASO 1 — Token Moodle

Usa la herramienta MCP `check_auth`.

- ✅ `status: ok` → muestra sitio y usuario.
- ❌ `status: error` → indica al usuario:
  ```
  ⚠ Token caducado. Actualiza MOODLE_TOKEN en .env.
  ```

---

## PASO 2 — Snapshot reciente

Usa la herramienta MCP `get_latest_snapshot`.

Muestra una línea resumen:
```
Snapshot: YYYY-MM-DD  |  N datasets  |  N KB total
```

Si `status: no_snapshots` → indica que hay que ejecutar `/training-reports-ingest`.

---

## PASO 3 — Últimas acciones

Usa la herramienta MCP `get_audit_log` con `limit=10`.

Muestra tabla con las últimas 10 acciones:

| Timestamp | Acción | Detalle |
|---|---|---|
| 2026-05-25T06:00Z | ingest | 10 datasets |
| 2026-05-25T10:30Z | compliance | blanqueo → 126 completados |

Si el log está vacío → "Sin acciones registradas".

---

## PASO 4 — Diagnóstico

Muestra un resumen de una línea:
- ✅ **Sistema operativo** — token válido, snapshot de hoy disponible
- ⚠ **Atención** — snapshot antiguo (>1 día) o token próximo a caducar
- ❌ **Acción requerida** — token inválido o sin snapshots

Sugiere el siguiente comando según el estado.
