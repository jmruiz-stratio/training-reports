# Training Reports — Arquitectura y datos

Automatización de informes de formación: extracción diaria desde Moodle, sesiones del entorno de prácticas, y exportación a Excel.

---

## Qué hay instalado y dónde

### 1. Moodle — `training.stratio.com`

Plugin PHP **`local_stratiorep`** instalado en el servidor Moodle.
Expone 7 funciones de extracción bulk que la API estándar de Moodle no cubre:

| Función | Qué devuelve |
|---|---|
| `get_users` | Todos los usuarios (email, username, fechas) |
| `get_cohort_members` | Miembros de cohorte con `timeadded` |
| `get_attendance_sessions` | Horas de asistencia por usuario/curso |
| `get_enrol_cohort_course` | Puente cohorte → curso |
| `get_all_grades` | Notas finales de curso en una sola llamada |
| `get_user_enrollments` | Inscripciones activas |
| `get_course_completions` | Completions de cursos |

Código fuente: `moodle_plugin/`

---

### 2. Kubernetes — cluster `certspractices.int`

#### Namespace `keos-auth`
- **oauth2-proxy** (existente, no gestionado aquí): proxy de autenticación OIDC para el entorno de prácticas. Sus logs registran cada inicio de sesión (`[AuthSuccess]`), actividad (`/oauth2/auth`) y cierre de sesión (`sign_out`) de los alumnos.

#### Namespace `formacion-apps`
- **CronJob `practices-session-extractor`** (desplegado aquí): se ejecuta diariamente a las 06:00 UTC. Lee los logs del oauth2-proxy vía K8s API (cross-namespace, RBAC en `keos-auth`), extrae las sesiones de alumnos y las indexa en OpenSearch.
  - Código fuente del script: `k8s/practices-extractor/script.py`
  - Manifiesto K8s: `k8s/practices-extractor/cronjob.yaml`
  - RBAC: `k8s/practices-extractor/rbac.yaml`

#### Namespace `formacion-datastores`
- **OpenSearch 2.13** (existente): almacena el índice `practices_sessions` con las sesiones extraídas.
- **OpenSearch Dashboards** (existente): dashboard "Sesiones de Prácticas" disponible en `https://admin.formacion.practices.stratio.com/opensearch-dashboards.formacion-datastores`

---

### 3. HDFS — `admin.practices.stratio.com` (Stratio)

Destino de los snapshots Parquet de Moodle.
Ruta: `/informes/moodle/{dataset}/ingest_date=YYYY-MM-DD/`

> ⏳ La subida diaria está implementada (`training-batch ingest daily`) pero aún no tiene cron configurado en el scheduler del equipo.

---

### 4. Máquina local / CI

Scripts Python que generan el informe. Requieren:
- `.venv` con dependencias (`pip install -e .[dev]`)
- `.env` con credenciales (ver `.env.example`)
- Para datos de prácticas: port-forward al OpenSearch del cluster

---

## Flujo de datos

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  MOODLE (training.stratio.com)                                               │
│  Plugin local_stratiorep — 7 funciones bulk                                 │
└────────────────────┬────────────────────────────────────────────────────────┘
                     │  training-batch ingest daily (diario, manual por ahora)
                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  SNAPSHOT LOCAL  /tmp/moodle-reports-agent/YYYY-MM-DD/                      │
│  10 ficheros Parquet (users, courses, cohorts, grades, completions…)        │
└──────────┬──────────────────────────────────────────────────────────────────┘
           │  (pendiente: subida a HDFS vía Rocket API)
           ▼
┌──────────────────────────┐
│  HDFS /informes/moodle/  │  ← destino final para Spark/Metabase (pendiente)
└──────────────────────────┘


┌─────────────────────────────────────────────────────────────────────────────┐
│  ENTORNO DE PRÁCTICAS (K8s cluster certspractices.int)                      │
│  oauth2-proxy en keos-auth → logs de sesión de alumnos                     │
└────────────────────┬────────────────────────────────────────────────────────┘
                     │  CronJob practices-session-extractor (06:00 UTC diario)
                     │  Lee logs vía K8s API (cross-namespace RBAC)
                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  OPENSEARCH  índice practices_sessions  (formacion-datastores)              │
│  Campos: email, user, partner, tenant, fecha_inicio, fecha_fin,             │
│          last_seen, groups                                                  │
│  157 sesiones indexadas (actualizado diariamente)                           │
└────────────────────┬────────────────────────────────────────────────────────┘
                     │  python3 src/download_practices.py
                     ▼
                reports/sesiones_practicas.csv


┌──────────────────────────────────────────────────────────────────────────────┐
│  GENERACIÓN DEL INFORME (local)                                              │
│                                                                              │
│  Snapshot Parquet  ──┐                                                       │
│  sesiones_practicas  ├──► python3 src/local_validate.py ──► Excel (9 hojas) │
│  partners_meta.csv  ──┘                                                      │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## Estado operativo

| Componente | Estado |
|---|---|
| Plugin Moodle `local_stratiorep` | ✅ Instalado |
| Extracción Moodle → Parquet local | ✅ Operativo |
| CronJob prácticas → OpenSearch | ✅ Desplegado, corre diariamente |
| Dashboard OpenSearch Dashboards | ✅ Activo |
| Generación Excel (9 hojas) | ✅ Operativo |
| Subida Parquet a HDFS | ⏳ Implementado, sin cron |
| Capa semántica en Stratio (Spark) | ⏳ SQL listo, ejecución pendiente |
| Dashboards Metabase | ⏳ Pendiente URL y versión |

---

## Comandos del día a día

Ejecutar siempre desde la raíz del repo (donde vive el `.env`):

```bash
# ── Actualizar el informe completo ────────────────────────────────────────────

# 1. Extraer datos frescos de Moodle
python3 -m batch_agent ingest daily --skip-upload

# 2. Descargar sesiones de prácticas (requiere port-forward al cluster)
kubectl port-forward -n formacion-datastores svc/opensearch-coordinator 19200:9200
python3 src/download_practices.py

# 3. Generar Excel (9 hojas)
python3 src/local_validate.py

# ── Otras operaciones ─────────────────────────────────────────────────────────

# Subir snapshot a HDFS
python3 -m batch_agent ingest daily

# Validar snapshot
python3 -m batch_agent validate snapshot /tmp/moodle-reports-agent/YYYY-MM-DD

# Comparar dos días
python3 -m batch_agent compare snapshots /tmp/.../YYYY-MM-DD /tmp/.../YYYY-MM-DD

# Forzar re-indexado de prácticas (CronJob manual)
kubectl create job -n formacion-apps --from=cronjob/practices-session-extractor reindex-$(date +%s)

# Actualizar ConfigMap del script de prácticas tras cambiar script.py
kubectl create configmap practices-extractor-script \
  --from-file=script.py=k8s/practices-extractor/script.py \
  -n formacion-apps --dry-run=client -o yaml | kubectl apply -f -
```

---

## Hojas del Excel generado

| Hoja | Contenido |
|---|---|
| `resumen_ejecutivo` | KPIs globales (usuarios, certificaciones, horas…) |
| `resumen_partner` | Una fila por partner con todos sus KPIs + desglose por año |
| `evolucion_mensual` | Altas, inscritos, certificados y horas por partner y mes |
| `partner_categoria` | Alumnos y aprobados por partner × categoría |
| `partner_version` | Alumnos y aprobados por partner × versión × curso |
| `detalle_certificados` | Fila por alumno aprobado (nota, fecha) |
| `alertas` | Partners sin actividad >30 días |
| `sesiones_practicas` | Sesiones individuales del entorno de prácticas |
| `resumen_practicas` | Resumen por partner: sesiones, alumnos únicos, horas |

---

## Recursos K8s (entorno de prácticas)

| Recurso | Namespace | Nombre |
|---|---|---|
| CronJob | formacion-apps | practices-session-extractor |
| ServiceAccount | formacion-apps | practices-extractor |
| ConfigMap | formacion-apps | practices-extractor-script |
| Secret (TLS admin) | formacion-apps | opensearch-admin-tls |
| Role | keos-auth | practices-extractor-log-reader |
| RoleBinding | keos-auth | practices-extractor-log-reader |

---

## Estructura del repositorio

```
training-reports/
├── CLAUDE.md                 # Contexto maestro completo (arquitectura, reglas SQL, decisiones)
├── RUNBOOK.md                # Guía operativa paso a paso
├── moodle_plugin/            # Plugin PHP local_stratiorep
├── python_core/              # Núcleo Python: extracción, storage, validación, reglas
├── batch_agent/              # CLI ingesta diaria
├── skill/                    # CLI analítica local (KPIs, CSV, Excel)
├── mcp_server/               # MCP server para Claude Code
├── src/
│   ├── local_validate.py     # Generador principal del Excel (DuckDB + openpyxl)
│   ├── download_practices.py # Descarga practices_sessions de OpenSearch → CSV
│   ├── create_practices_dashboard.py  # Crea/actualiza dashboard en OpenSearch Dashboards
│   ├── transform/semantic/   # SQL Spark — capa semántica (dim_* + f_*)
│   ├── transform/reporting/  # SQL Spark — capa reporting (r_*)
│   └── data/partners_meta.csv
├── k8s/practices-extractor/  # CronJob + RBAC + script del extractor de prácticas
└── reports/                  # Salida local (Excel, CSVs) — en .gitignore
```

---

## Documentación de referencia

- `CLAUDE.md` — Arquitectura completa, reglas de negocio, modelo semántico, histórico de decisiones
- `RUNBOOK.md` — Guía operativa detallada (setup, preprod, prod)
