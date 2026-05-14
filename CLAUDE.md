# Training Reports — Contexto maestro del proyecto

> Este fichero es la fuente de verdad para cualquier agente Claude (Claude Code, VS Code, desktop) que trabaje en el repo. Contiene objetivo, arquitectura, reglas de negocio, convenciones y estado actual. **Mantenlo vivo: si cambia una decisión, se edita aquí.**

---

## 1. Objetivo

Automatizar la generación de los informes de formación que hoy se hacen a mano ejecutando consultas contra Moodle y volcándolas en un Google Sheet.

**Destino final:**
1. **Capa RAW** en HDFS — Parquet extraídos vía API REST de Moodle (snapshot diario).
2. **Capa semántica** en Stratio Data Fabric — Spark SQL sobre HDFS (ejecución única).
3. **Capa reporting** — tablas agregadas servidas a Metabase.
4. **Dashboards en Metabase** que sustituyen al Google Sheet.

Stakeholders: Alberto y Alex principalmente; dirección consume los dashboards finales.

---

## 2. Arquitectura por capas

```
┌──────────────────────────────────────────────────────────────┐
│  MOODLE — API REST (wstoken)                                  │
│  Plugin local_stratiorep (7 funciones bulk custom)           │
└─────────────────────┬────────────────────────────────────────┘
                      │  training-batch ingest daily
                      ▼
┌──────────────────────────────────────────────────────────────┐
│  CAPA RAW (HDFS /informes/moodle/{dataset}/ingest_date=…)    │
│  Parquet snappy, snapshot diario full, solo el último        │
└─────────────────────┬────────────────────────────────────────┘
                      │  Spark SQL (una vez)
                      ▼
┌──────────────────────────────────────────────────────────────┐
│  CAPA SEMÁNTICA (Stratio)                                     │
│  dim_partners, dim_cohortes, dim_cursos                      │
│  f_usuarios, f_inscripciones, f_certificaciones,             │
│  f_actividad, f_dedicacion                                   │
└─────────────────────┬────────────────────────────────────────┘
                      │  agregaciones
                      ▼
┌──────────────────────────────────────────────────────────────┐
│  CAPA REPORTING                                               │
│  r_resumen_partner, r_evolucion_mensual, r_partner_categoria │
│  r_partner_version, r_detalle_certificados, r_alertas        │
└─────────────────────┬────────────────────────────────────────┘
                      ▼
                  METABASE
```

**Validación local (sin Stratio):** `training-skill reporting` ejecuta la capa semántica + reporting en DuckDB sobre los Parquet locales y exporta Excel+CSV. Permite validar KPIs antes de subir a HDFS.

---

## 3. Estructura del repositorio

```
training-reports/
├── CLAUDE.md                    # ← este fichero
├── README.md                    # overview + comandos principales
├── RUNBOOK.md                   # guía operativa dev/preprod/prod
├── pyproject.toml               # dependencias + scripts de paquete
├── .env.example                 # variables de entorno (sin secretos)
├── .claude/settings.json        # MCP server autoarranque en Claude Code
│
├── moodle_plugin/               # Plugin PHP local_stratiorep
│   ├── externallib.php          # 7 funciones implementadas
│   ├── db/services.php          # registro de funciones
│   ├── db/access.php
│   ├── version.php
│   └── lang/en/local_stratiorep.php
│
├── python_core/                 # Núcleo reutilizable
│   ├── config.py                # load_settings(), DATASETS_ALL
│   ├── auth.py                  # cookies Rocket (login OAuth2-proxy)
│   ├── extraction.py            # Extractor + run_all (con caché)
│   ├── moodle_client.py         # thin wrapper sobre shared.moodle_api
│   ├── utils.py                 # log()
│   ├── domain/rules.py          # regla canónica de partner
│   ├── storage/parquet.py       # write(), row_count()
│   ├── storage/hdfs.py          # put(), list_path(), delete_*()
│   └── validation/
│       ├── technical.py         # row counts + checksum SHA-256
│       └── sanity.py            # KPIs DuckDB + compare_snapshot_counts()
│
├── batch_agent/                 # CLI operativa diaria
│   ├── cli.py                   # ingest daily | validate snapshot | compare snapshots
│   └── runner.py                # ingest_daily(), _upload_parquets()
│
├── skill/                       # CLI analítica local
│   ├── cli.py                   # kpis | export | reporting
│   └── analytics.py             # partner_kpis(), export_reporting_package()
│
├── mcp_server/                  # MCP server (Claude Code)
│   ├── server.py                # FastMCP con 4 tools
│   └── tools.py                 # list_training_partners, get_partner_kpis, …
│
├── shared/                      # Compatibilidad legacy (no tocar)
│   ├── moodle_api.py            # _moodle_call + todas las funciones API
│   ├── practices_auth.py        # login OAuth2-proxy + Selenium fallback
│   └── utils.py                 # load_env, log
│
├── src/
│   ├── agent/main.py            # shim de compatibilidad (→ batch_agent)
│   ├── agent/extract.py         # orquestador legacy (referencia de fallbacks)
│   ├── agent/sanity.py          # validación negocio legacy (DuckDB)
│   ├── agent/upload_hdfs.py     # subida HDFS (referenciado por python_core/storage/hdfs.py)
│   ├── data/partners_meta.csv   # metadatos de negocio por partner
│   ├── local_validate.py        # validación local semántica + reporting (DuckDB → Excel)
│   ├── refresh_cookies.py       # renovación cookies Rocket en .env
│   ├── diagnostico/             # check previo de funciones Moodle
│   └── transform/
│       ├── semantic/            # 8 SQL Spark (dim_* + f_*)
│       └── reporting/           # 6 SQL Spark (r_*)
│
└── tests/                       # pytest
    ├── test_partner_rule.py     # regla canónica partner (11 casos)
    ├── test_pagination.py       # paginación Moodle
    ├── test_core_rules.py
    ├── test_batch_runner.py
    ├── test_skill_reporting.py
    └── test_mcp_tools_smoke.py
```

---

## 4. Datasets RAW

10 datasets extraídos diariamente. Estrategia: **custom first → standard → N+1 optimizado**.

| Dataset | Función primaria | Fallback | Strategy |
|---|---|---|---|
| `users` | `local_stratiorep_get_users` | `core_user_get_users` → IDs vía `cohort_members_ext` → enrolled por curso | Full |
| `courses` | `core_course_get_courses` | — | Full |
| `cohorts` | `core_cohort_get_cohorts` | Deriva IDs desde `cohort_members_ext` (sin nombres) | Full |
| `cohort_members` | `core_cohort_get_cohort_members` | — | N+1 por cohorte |
| `user_courses` | `local_stratiorep_get_user_enrollments` | `core_enrol_get_users_courses` N+1 por usuario | Full |
| `user_grades` | `local_stratiorep_get_all_grades` | N+1 optimizado por pares (userid, courseid) inscritos | Full |
| `course_completions` | `local_stratiorep_get_course_completions` | N+1 optimizado por pares inscritos | Full |
| `cohort_members_ext` | `local_stratiorep_get_cohort_members` | — | Full |
| `attendance_sessions` | `local_stratiorep_get_attendance_sessions` | — | Full |
| `enrol_cohort_course` | `local_stratiorep_get_enrol_cohort_course` | — | Full |

**Tabla maestra estática:** `src/data/partners_meta.csv` — `partner`, `tipo`, `region`, `trajo_oportunidades`, `trajo_clientes`, `paga_certificacion`, `total_pagado`. Se sube a HDFS una sola vez como CSV.

---

## 5. Plugin Moodle `local_stratiorep` — ✅ INSTALADO

7 funciones en `moodle_plugin/externallib.php`. Todas registradas en `db/services.php`.

| Función | SQL | Motivo |
|---|---|---|
| `get_users` | `SELECT id,username,email,firstname,lastname,timecreated,lastaccess,suspended FROM mdl_user WHERE deleted=0 AND id>1` | Extracción ligera en una sola llamada |
| `get_cohort_members` | `SELECT CONCAT(cohortid,'_',userid) AS recid, cohortid, userid, timeadded FROM mdl_cohort_members` | `core_cohort_get_cohort_members` no devuelve `timeadded`; `CONCAT` como primera columna evita el bug de `get_records_sql` que colapsaba 33.549 filas a 49 |
| `get_attendance_sessions` | `SELECT s.userid, r.course AS courseid, s.login, s.duration FROM mdl_attendanceregister_session s JOIN mdl_attendanceregister r ON r.id=s.register` | Plugin `attendanceregister` no expone webservices |
| `get_enrol_cohort_course` | `SELECT customint1 AS cohortid, courseid FROM mdl_enrol WHERE enrol='cohort'` | Puente cohorte→curso no expuesto en API estándar |
| `get_all_grades` | `SELECT gg.userid, gi.courseid, gg.finalgrade AS graderaw, gg.timemodified AS gradedategraded FROM mdl_grade_grades gg JOIN mdl_grade_items gi ON gi.id=gg.itemid WHERE gi.itemtype='course' AND gg.finalgrade IS NOT NULL` | Evita N+1 (~4.000 llamadas); usa `finalgrade` (no `rawgrade`) para `itemtype='course'` |
| `get_user_enrollments` | `SELECT CONCAT(ue.userid,'_',e.courseid) AS id, ue.userid, e.courseid FROM mdl_user_enrolments ue JOIN mdl_enrol e ON e.id=ue.enrolid WHERE ue.status=0 AND e.status=0` | Reemplaza N+1 de inscripciones |
| `get_course_completions` | `SELECT id, userid, course AS courseid, CASE WHEN timecompleted>0 THEN 1 ELSE 0 END AS completed, timecompleted FROM mdl_course_completions` | Reemplaza N+1 de completions |

**Funciones estándar en el token:** solo `core_cohort_get_cohorts` es necesaria (disponible). Las demás funciones estándar están reemplazadas por el plugin.

---

## 6. Reglas de negocio canónicas

### 6.1 Regla de `partner` (centralizada en `python_core/domain/rules.py`)

```sql
-- Spark SQL / DuckDB
CASE
  WHEN LOWER(email)    LIKE '%stratio%'
    OR LOWER(username) LIKE '%stratio%' THEN 'stratio'
  ELSE reverse(split(reverse(username), '-')[0])   -- Spark
  -- ELSE reverse(string_split(reverse(username), '-')[1])  -- DuckDB (1-indexed)
END
```

### 6.2 Categoría de cohorte/curso

```sql
CASE
  WHEN LOWER(name) LIKE '%governance%'      THEN 'Governance'
  WHEN LOWER(name) LIKE '%data processing%' THEN 'Data Processing'
  WHEN LOWER(name) LIKE '%intelligence%'    THEN 'Intelligence'
  WHEN LOWER(name) LIKE '%operaciones%'     THEN 'Operaciones'
  ELSE 'Otros'
END
```

### 6.3 Versión

```sql
NULLIF(regexp_extract(name, '(1[34]\\.[0-9])', 1), '')
```

### 6.4 Idioma

Sufijo del nombre: ` - ES` → ES, ` - EN` → EN, ` - FR` → FR.

### 6.5 Aprobado de certificación

`finalgrade >= 70`. Solo aplica a cursos donde `es_certificacion = TRUE`.

### 6.6 Curso de certificación

`LOWER(fullname) LIKE '%certificaci%' OR LOWER(fullname) LIKE '%certification%'`

---

## 7. Modelo semántico (Spark SQL, ejecución única en Stratio)

SQL en `src/transform/semantic/`. Equivalente DuckDB en `src/local_validate.py`.

### Dimensiones

**`dim_partners`** — todos los partners distintos enriquecidos con `partners_meta.csv`:
`partner`, `tipo`, `region`, `trajo_oportunidades`, `trajo_clientes`, `paga_certificacion`, `total_pagado`

**`dim_cohortes`** — `cohort_id`, `cohort_name`, `categoria`, `version`, `idioma`, `visible`

**`dim_cursos`** — `course_id`, `course_name`, `es_certificacion`, `categoria`, `version`, `idioma`

### Hechos

**`f_usuarios`** — `userid`, `username`, `email`, `nombre_completo`, `partner`, `fecha_alta`, `ultimo_acceso`, `activo`

**`f_inscripciones`** — `userid`, `cohort_id`, `partner`, `categoria`, `version`, `fecha_inscripcion`, `mes_inscripcion` *(requiere `cohort_members_ext`)*

**`f_certificaciones`** ⭐ — `userid`, `course_id`, `partner`, `finalgrade`, `aprobado`, `fecha_nota` *(solo cursos `es_certificacion=TRUE`)*

**`f_actividad`** — `userid`, `course_id`, `partner`, `tiene_actividad`, `primer_acceso`, `ultimo_acceso`

**`f_dedicacion`** — `userid`, `course_id`, `partner`, `mes`, `horas` *(desde `attendance_sessions`)*

---

## 8. Modelo reporting (Spark SQL, ejecución única en Stratio)

SQL en `src/transform/reporting/`. Las mismas queries corren en DuckDB vía `training-skill reporting`.

| Tabla | Contenido | Columnas clave |
|---|---|---|
| `r_resumen_partner` | Una fila por partner con todos sus KPIs + desglose por año | `partner`, `tipo`, `region`, `total_altas`, `altas_YYYY`, `total_inscritos`, `total_certificados`, `total_horas`, `horas_YYYY`, `ultimo_acceso` |
| `r_evolucion_mensual` | Altas, inscritos, certificados y horas por partner y mes | `partner`, `mes`, `altas`, `inscritos`, `certificados`, `horas` |
| `r_partner_categoria` | Alumnos y aprobados por partner × categoría | `partner`, `categoria`, `alumnos`, `aprobados` |
| `r_partner_version` | Alumnos y aprobados por partner × versión × categoría × curso | `partner`, `version`, `categoria`, `course_name`, `alumnos`, `aprobados` |
| `r_detalle_certificados` | Fila por usuario aprobado | `userid`, `username`, `nombre_completo`, `partner`, `course_name`, `finalgrade`, `fecha_nota` |
| `r_alertas` | Partners sin actividad >30 días | `partner`, `ultimo_acceso`, `dias_sin_actividad` |

---

## 9. Variables de entorno

```bash
# Extracción Moodle (obligatorio)
MOODLE_URL=https://<tu-moodle>
MOODLE_TOKEN=<token>

# Subida HDFS — opción A: cookies directas
STRATIO_URL=https://<tu-stratio>
STRATIO_COOKIE=<cookie>
JSESSIONID=<jsession>

# Subida HDFS — opción B: login (genera cookies automáticamente)
STRATIO_URL=https://<tu-stratio>
STRATIO_USER=<user>
STRATIO_PASS=<pass>
STRATIO_TENANT=formacion       # opcional, default formacion

# Opcionales
HDFS_BASE_PATH=/informes/moodle          # default
AGENT_WORKDIR=/tmp/moodle-reports-agent  # default
```

---

## 10. Comandos y entrypoints

### Operación diaria

```bash
# Ingesta completa (extrae + valida + sube a HDFS)
training-batch ingest daily

# Solo local, sin subir
training-batch ingest daily --skip-upload

# Validar un snapshot
training-batch validate snapshot /tmp/moodle-reports-agent/2026-04-23

# Comparar dos días
training-batch compare snapshots /tmp/.../2026-04-22 /tmp/.../2026-04-23
```

### Analítica local

```bash
# Excel completo (6 hojas)
training-skill reporting /tmp/moodle-reports-agent/2026-04-23

# Excel solo para un partner
training-skill reporting /tmp/moodle-reports-agent/2026-04-23 --partner pichincha

# KPIs rápidos en JSON
training-skill kpis /tmp/moodle-reports-agent/2026-04-23

# También disponible directamente:
python3 src/local_validate.py [--partner pichincha] [--workdir ...] [--output ...]
```

### Compatibilidad legacy

```bash
python3 -m src.agent.main --date 2026-04-23 --skip-upload
```

### Cookies Rocket

```bash
python3 src/refresh_cookies.py   # renueva STRATIO_COOKIE + JSESSIONID en .env
```

---

## 11. MCP server (Claude Code)

El servidor MCP está configurado en `.claude/settings.json` y arranca automáticamente al abrir el proyecto en Claude Code. Implementa el protocolo MCP estándar con FastMCP.

**Tools disponibles:**

| Tool | Parámetros | Qué hace |
|---|---|---|
| `list_training_partners` | `workdir` | Lista todos los partners del snapshot |
| `get_partner_kpis` | `workdir`, `partner` | KPIs de un partner concreto |
| `validate_latest_snapshot` | `workdir` | Row counts y KPIs de negocio del snapshot |
| `compare_snapshots` | `base_dir`, `target_dir` | Deltas de row counts entre dos días |

**Uso:** solo funciona en **Claude Code** (CLI/VSCode), no en claude.ai web. Lee Parquet locales — no descarga de HDFS.

**Flujo típico:**
```bash
training-batch ingest daily --skip-upload   # genera snapshot local
# abrir proyecto en Claude Code → MCP arranca solo
# "¿cuántos usuarios tiene pichincha?"
```

---

## 12. KPIs del último snapshot real (2026-04-22)

| Métrica | Valor |
|---|---|
| Partners | 149 |
| Usuarios totales | 4.252 |
| Usuarios activos | 2.926 |
| Cohortes | 49 |
| Cursos totales | 221 |
| Cursos certificación | 60 |
| Inscripciones (cohort) | 33.549 |
| Notas de curso | 5.383 |
| Certificaciones aprobadas (≥70) | 2.499 |
| Sesiones asistencia | 237.515 |
| Horas totales | 49.276 |

---

## 13. Decisiones tomadas

| # | Decisión | Fecha |
|---|---|---|
| 1 | Umbral de aprobado: `finalgrade >= 70` | 2026-04-21 |
| 2 | Estrategia extracción: API REST estándar + plugin `local_stratiorep` para lo que no cubre la API | 2026-04-21 |
| 3 | Frecuencia ingesta RAW: diaria, full-snapshot, solo el último | 2026-04-21 |
| 4 | Motor semántica: Spark SQL sobre HDFS (construcción única) | 2026-04-21 |
| 5 | `partners_meta`: tabla maestra estática (`src/data/partners_meta.csv`), subida una vez | 2026-04-21 |
| 6 | Aprobación solo aplica a certificaciones; cohorte es descriptiva | 2026-04-21 |
| 7 | Validación local pre-Stratio: DuckDB + openpyxl (`training-skill reporting`) | 2026-04-22 |
| 8 | Funciones estándar Moodle no necesarias en token: sustituidas por plugin custom | 2026-04-22 |
| 9 | MCP server: protocolo MCP real con FastMCP (no dispatcher casero) | 2026-04-23 |
| 10 | `run_all` distingue access_denied (skip) de errores reales (stop pipeline) | 2026-04-23 |
| 11 | Ejecución de SQL en Stratio: mecanismo pendiente de confirmar (se recibirán ficheros de ejemplo) | 2026-04-23 |

---

## 14. Roadmap y estado actual

### ✅ Completado

- Plugin `local_stratiorep` instalado y operativo (7 funciones).
- Extracción completa probada localmente (10 datasets, KPIs verificados).
- Capa semántica + reporting en DuckDB (`training-skill reporting` / `src/local_validate.py`).
- `partners_meta.csv` integrado (tipo, región, oportunidades, certificación, pagado).
- Validación Excel generada y comparada contra Google Sheet original.
- Arquitectura modular: `python_core`, `batch_agent`, `skill`, `mcp_server`.
- MCP server con protocolo real (FastMCP), configurado en `.claude/settings.json`.

### ⏳ Siguiente paso inmediato

**Subir primer snapshot a HDFS:**
```bash
python3 src/refresh_cookies.py
training-batch ingest daily
```

### 🔲 Pendiente

- **Capa semántica en Stratio**: mecanismo de ejecución SQL pendiente de confirmar (se recibirán ficheros de ejemplo del entorno). Adaptar `src/deploy/run_transforms.py` según lo que se vea.
- **Metabase**: cards/preguntas automatizables vía API REST de Metabase (script Python); layout del dashboard a mano. Pendiente de URL y versión de Metabase.
- **Cron diario**: `training-batch ingest daily` en el scheduler del equipo.

---

## 15. Convenciones

- **Idioma:** identificadores en inglés, comentarios en castellano.
- **Fechas:** `YYYY-MM-DD` en particiones, `YYYY-MM` en agregados mensuales.
- **SQL semántico:** Spark SQL en `src/transform/`. DuckDB en `src/local_validate.py` (misma lógica, dialecto diferente).
- **Diferencias Spark↔DuckDB:** `from_unixtime(x)` → `to_timestamp(x)`; `split(x,'-')[0]` → `string_split(x,'-')[1]` (DuckDB es 1-indexed); `date_format(x,'yyyy-MM')` → `strftime(x,'%Y-%m')`.
- **Código Python:** stdlib (`urllib`, `json`) + `pyarrow`, `duckdb`, `openpyxl`, `mcp`. Sin `requests`, sin `pandas`.
- **Grano de aprobación:** `f_certificaciones` — no usar `user_grades` directamente.
- **Regla de partner:** usar siempre `python_core.domain.rules` o la expresión SQL de §6.1. No duplicar.
