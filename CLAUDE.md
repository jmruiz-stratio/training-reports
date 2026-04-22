# Proyecto: Agente de automatización de informes de formación (Moodle → Stratio Data Fabric → Metabase)

> **Versión 3** — extracción vía **API REST de Moodle** (opción C: API estándar + funciones custom para lo que falta). Reutiliza patrones del proyecto hermano `training-agents` (estructura modular, urllib stdlib, cargador .env casero, diagnóstico previo).
>
> Este fichero es el contexto maestro del proyecto. Cualquier agente Claude (VS Code, Claude Code, desktop) que lo lea debe poder entender el objetivo, la arquitectura, las convenciones y el estado actual sin preguntar. Mantenlo vivo: si cambia una decisión, se edita aquí.

---

## 1. Objetivo

Automatizar la generación de los informes de formación que hoy se hacen a mano ejecutando consultas contra Moodle y volcándolas en un Google Sheet.

Destino:

1. **Capa RAW** en HDFS (JSON/Parquet extraídos vía API REST de Moodle).
2. **Capa SEMÁNTICA** en Stratio Data Fabric, construida con **Spark SQL**.
3. **Capa REPORTING** (tablas agregadas) servida a Metabase.
4. **Dashboards en Metabase** que sustituyen al Google Sheet.

Stakeholders: Alberto y Alex principalmente; dirección consume los dashboards finales.

### Alcance del agente

El agente **solo cubre la capa RAW**: extracción diaria vía API REST de Moodle y carga/validación en HDFS (API de Rocket). Las capas semántica y reporting se construyen **una sola vez** sobre Stratio y se dejan desplegadas: viven en el mismo repo (versionadas y reproducibles) pero no se refrescan a diario.

---

## 2. Contexto previo

- Fichero `consultas_informe_alberto.txt` con ~15 consultas SQL en **dialecto PostgreSQL** contra `mdl_*`. **Ya no se ejecutan tal cual**; son referencia semántica de qué hay que calcular.
- Google Sheet con 21 bloques resultado manual de esas consultas + metadatos de negocio pegados a mano.
- Proyecto hermano `training-agents` (ruta local: `/home/jmruiz/datos/repos/training-agents`) del que **reutilizamos** patrones de código y autenticación.

### Reutilización desde `training-agents`

| Pieza | Dónde vive allá | Qué reutilizamos |
|---|---|---|
| Cargador `.env` sin dependencias | `shared/utils.py::load_env` | Copiar tal cual |
| Cliente HTTP Moodle | `moodle/moodle_api.py::_moodle_call` | Copiar tal cual + ampliar con funciones nuevas |
| Diagnóstico Moodle | `diagnostico_moodle.py` | Adaptar con la lista de funciones que necesitamos |
| Autenticación Stratio (tenant `formacion`) | `get_stratio_token.py`, `get_practices_cookies.py` | Copiar tal cual para obtener tokens/cookies para la API de Rocket |
| Convención: solo stdlib (`urllib`, `json`) | Todo el proyecto | Mantener la misma convención |

---

## 3. Arquitectura por capas

```
┌──────────────────────────────────────────────────────────────────┐
│  MOODLE — accedido SOLO vía API REST (webservice/rest/server.php) │
│  Auth: wstoken (MOODLE_TOKEN)                                     │
│  + fichero partners_meta.csv — tabla maestra (fase futura: UI)    │
└──────────────────────────────┬───────────────────────────────────┘
                               │  agente: llamadas REST paginadas
                               │  → JSON/Parquet local → API Rocket → HDFS
                               │  (diario, full-snapshot)
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│  CAPA RAW (HDFS en Stratio, tenant formacion)                     │
│  /informes/moodle/{dataset}/ingest_date=YYYY-MM-DD/*.parquet      │
│  /informes/business/partners_meta/partners_meta.csv               │
│  Snapshot diario. Inmutable. Conservamos solo el último.          │
└──────────────────────────────┬───────────────────────────────────┘
                               │  Spark SQL — construcción ÚNICA
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│  CAPA SEMÁNTICA (Stratio — Spark SQL sobre HDFS)                  │
│  Dimensiones: dim_partners, dim_cohortes, dim_cursos              │
│  Hechos:      f_usuarios, f_inscripciones, f_certificaciones,     │
│               f_actividad, f_dedicacion                           │
└──────────────────────────────┬───────────────────────────────────┘
                               │  agregaciones para dashboard
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│  CAPA REPORTING (tablas agregadas)                                │
│  r_resumen_partner, r_evolucion_mensual, r_partner_categoria, ... │
└──────────────────────────────┬───────────────────────────────────┘
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│  METABASE — dashboards                                            │
└──────────────────────────────────────────────────────────────────┘
```

---

## 4. Estructura del repositorio

```
moodle-reports-agent/
├── CLAUDE.md                          # este fichero
├── README.md                          # arranque, ejecución, contribución
├── .env.example                       # variables de entorno (sin secretos)
├── pyproject.toml                     # dependencias mínimas (pyarrow para parquet)
│
├── src/
│   ├── agent/                         # ⭐ núcleo: agente diario
│   │   ├── main.py                    # punto de entrada
│   │   ├── config.py                  # carga .env, constantes
│   │   ├── extract.py                 # orquesta las llamadas REST por dataset
│   │   ├── to_parquet.py              # JSON → Parquet local
│   │   ├── upload_hdfs.py             # API de Rocket (§9.6)
│   │   ├── validate.py                # row counts + checksums
│   │   └── report.py                  # resumen de la ejecución
│   │
│   ├── shared/                        # reutilizable (copiado de training-agents)
│   │   ├── utils.py                   # load_env, log
│   │   └── moodle_api.py              # _moodle_call + funciones por dataset
│   │
│   ├── diagnostico/
│   │   └── diagnostico_moodle.py      # check previo (adaptado, §9.9)
│   │
│   ├── transform/                     # se ejecuta UNA VEZ sobre Stratio
│   │   ├── semantic/
│   │   │   ├── dim_partners.sql
│   │   │   ├── dim_cohortes.sql
│   │   │   ├── dim_cursos.sql
│   │   │   ├── f_usuarios.sql
│   │   │   ├── f_inscripciones.sql
│   │   │   ├── f_certificaciones.sql
│   │   │   ├── f_actividad.sql
│   │   │   └── f_dedicacion.sql
│   │   └── reporting/
│   │       ├── r_resumen_partner.sql
│   │       ├── r_evolucion_mensual.sql
│   │       ├── r_partner_categoria.sql
│   │       ├── r_partner_version.sql
│   │       ├── r_detalle_certificados.sql
│   │       └── r_alertas.sql
│   │
│   └── deploy/
│       └── run_transforms.py          # ejecución Spark SQL (una vez)
│
├── moodle_plugin/                     # funciones custom Moodle (§9.8)
│   ├── README.md                      # cómo desplegarlas
│   └── externallib.php                # funciones custom
│
├── sql_legacy/                        # consultas originales PostgreSQL (solo referencia)
│   └── consultas_informe_alberto.txt
│
├── notebooks/
├── tests/
└── docs/
    ├── data_dictionary.md
    ├── kpi_definitions.md
    └── lineage.md
```

---

## 5. Datasets RAW (capa 1)

Todos en HDFS, particionados por `ingest_date=YYYY-MM-DD`, formato **Parquet** salvo la tabla maestra (CSV).

### 5.1 Desde Moodle (snapshot diario vía API REST)

El agente consulta la API y convierte cada respuesta JSON a Parquet. Un dataset por respuesta lógica:

| Ruta HDFS | Función Moodle | Strategy | Clave |
|---|---|---|---|
| `/informes/moodle/users/` | `core_user_get_users` con `criteria=[{key:'deleted', value:'0'}]` o paginado | Full | `id` |
| `/informes/moodle/courses/` | `core_course_get_courses` | Full | `id` |
| `/informes/moodle/cohorts/` | `core_cohort_get_cohorts` | Full | `id` |
| `/informes/moodle/cohort_members/` | `core_cohort_get_cohort_members` (una llamada por cohorte) | N+1 | `(cohortid, userid)` |
| `/informes/moodle/user_courses/` | `core_enrol_get_users_courses` (una llamada por usuario) | N+1 | `(userid, courseid)` |
| `/informes/moodle/user_grades/` | `gradereport_user_get_grade_items` (una llamada por (usuario, curso)) | N+1 | `(userid, courseid, itemid)` |
| `/informes/moodle/course_completions/` | `core_completion_get_course_completion_status` (una llamada por (usuario, curso)) | N+1 | `(userid, courseid)` |
| `/informes/moodle/cohort_members_ext/` | **custom** `local_stratiorep_get_cohort_members` (§9.8) — incluye `timeadded` | Full | `(cohortid, userid)` |
| `/informes/moodle/attendance_sessions/` | **custom** `local_stratiorep_get_attendance_sessions` (§9.8) | Full | `(userid, courseid, login)` |
| `/informes/moodle/enrol_cohort_course/` | **custom** `local_stratiorep_get_enrol_cohort_course` (§9.8) — puente cohorte→curso | Full | `(cohortid, courseid)` |

> **Paginación**: las funciones estándar (`core_user_get_users`, `core_course_get_courses`…) pueden devolver listas grandes. El cliente debe paginar con `limitfrom`/`limitnum` (500 por página por defecto) y concatenar páginas.
>
> **N+1**: las funciones marcadas así se llaman una vez por cada item del dataset padre. Para ~100 usuarios × 40 cursos = 4.000 llamadas de notas. Es lento (minutos) pero aceptable en snapshot diario. Si hace falta optimizar, es candidato a reemplazar por una función custom que devuelva todo en una sola llamada.

### 5.2 Tabla maestra de negocio (estática)

| Ruta HDFS | Origen | Contenido |
|---|---|---|
| `/informes/business/partners_meta/partners_meta.csv` | Fichero subido una vez | `partner`, `tipo`, `region`, `trajo_oportunidades`, `trajo_clientes`, `paga_certificacion`, `total_pagado`, `notas` |

Decisión tomada: no se gestiona a diario. Gestión avanzada = evolución futura.

---

## 6. Modelo semántico (capa 2)

### 6.1 Dimensiones

#### `dim_partners`
```
partner             STRING   PK
tipo                STRING   -- Partner / Cliente / NULL
region              STRING
trajo_oportunidades BOOLEAN
trajo_clientes      BOOLEAN
paga_certificacion  BOOLEAN
total_pagado        DECIMAL(12,2)
notas               STRING
```

#### `dim_cohortes`
```
cohort_id    BIGINT PK
cohort_name  STRING
categoria    STRING   -- Governance | Data Processing | Intelligence | Operaciones | Otros
version      STRING   -- 13.0 | 13.2 | 14.0 | 14.1 | 14.6 | 14.8 | null
idioma       STRING   -- ES | EN | FR | null
visible      BOOLEAN
```

#### `dim_cursos`
```
course_id        BIGINT PK
course_name      STRING
es_certificacion BOOLEAN  -- nombre contiene 'certificación' o 'certification'
categoria        STRING
version          STRING
idioma           STRING
```

Reglas de derivación (sobre `fullname` / `name`):
- `es_certificacion`: `LOWER(x) LIKE '%certificación%' OR LOWER(x) LIKE '%certification%'`.
- `categoria`: `%Governance%` → Governance; `%Data Processing%` → Data Processing; `%Intelligence%` → Intelligence; `%Operaciones%` → Operaciones; resto → Otros.
- `version`: `regexp_extract(x, '(1[34]\\.[0-9])', 1)`; vacío → NULL.
- `idioma`: sufijo ` - ES`, ` - EN`, ` - FR`.

### 6.2 Hechos

#### `f_usuarios`
```
userid          BIGINT PK
username        STRING
email           STRING
nombre_completo STRING
partner         STRING   FK dim_partners
fecha_alta      TIMESTAMP
ultimo_acceso   TIMESTAMP
activo          BOOLEAN
```

**Regla canónica de `partner`**:
```sql
CASE
  WHEN LOWER(email) LIKE '%stratio%' OR LOWER(username) LIKE '%stratio%' THEN 'stratio'
  ELSE reverse(split(reverse(username), '-')[0])
END
```

#### `f_inscripciones`
Una fila por (usuario, cohorte). Requiere `cohort_members_ext` para tener `fecha_inscripcion`.
```
userid            BIGINT
cohort_id         BIGINT
partner           STRING
categoria         STRING
version           STRING
fecha_inscripcion TIMESTAMP
mes_inscripcion   STRING   -- YYYY-MM
PK (userid, cohort_id)
```

#### `f_certificaciones` ⭐
Solo cursos con `es_certificacion=TRUE`. Grano canónico de "aprobado".
```
userid       BIGINT
course_id    BIGINT
partner      STRING
finalgrade   DECIMAL(5,2)
aprobado     BOOLEAN   -- finalgrade >= 70
fecha_nota   TIMESTAMP
```

#### `f_actividad`
Placeholder para "curso finalizado" hasta cerrar criterio.
```
userid          BIGINT
course_id       BIGINT
partner         STRING
tiene_actividad BOOLEAN
primer_acceso   TIMESTAMP
ultimo_acceso   TIMESTAMP
```

#### `f_dedicacion`
Requiere `attendance_sessions` (función custom).
```
userid      BIGINT
course_id   BIGINT
partner     STRING
mes         STRING   -- YYYY-MM
horas       DECIMAL(8,2)
```

---

## 7. Capa reporting (capa 3) — KPIs para Metabase

| Vista | Pregunta | Sustituye hojas del Sheet |
|---|---|---|
| `r_resumen_partner` | Un número por partner: altas, inscritos, certificados, horas, última actividad | T1, T5 |
| `r_evolucion_mensual` | Altas / horas / usuarios activos / inscritos / certificados por (mes, partner) | T2, T3, T8, T9, T10 |
| `r_partner_categoria` | Certificados y únicos por partner × categoría | T13, T15, T19, T20 |
| `r_partner_version` | Matriz partner × versión | T12 |
| `r_detalle_certificados` | Una fila por certificación aprobada (auditoría) | T6, T7, T11 |
| `r_alertas` | Partners sin actividad en N días, cohortes con 0 certificados | nuevo |

---

## 8. Consultas / llamadas por capa

### 8.1 Extracción RAW (API REST Moodle) — las ejecuta el agente

Base URL: `{MOODLE_URL}/webservice/rest/server.php`
Auth: `wstoken={MOODLE_TOKEN}` en el body, junto con `wsfunction`, `moodlewsrestformat=json`.

**Patrón de llamada** (copiado de `training-agents/moodle/moodle_api.py::_moodle_call`):

```python
import json, urllib.request, urllib.parse

def moodle_call(moodle_url: str, token: str, wsfunction: str, **params) -> dict | list:
    body = urllib.parse.urlencode({
        "wstoken": token,
        "wsfunction": wsfunction,
        "moodlewsrestformat": "json",
        **{k: str(v) for k, v in params.items()},
    }).encode()
    req = urllib.request.Request(
        f"{moodle_url}/webservice/rest/server.php",
        data=body, method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        result = json.loads(r.read())
    if isinstance(result, dict) and "exception" in result:
        raise RuntimeError(f"Moodle [{wsfunction}]: {result.get('message', result)}")
    return result
```

**Llamadas por dataset** (pseudocódigo):

```python
# users
users = []
page = 0
while True:
    batch = moodle_call(url, tok, "core_user_get_users",
                        **{"criteria[0][key]": "deleted", "criteria[0][value]": "0"})
    # core_user_get_users no pagina: filtra por criterios. Si hay muchos, usar
    # core_user_get_users_by_field iterando por letras del abecedario o por ids.
    users = batch["users"]
    break

# courses
courses = moodle_call(url, tok, "core_course_get_courses")

# cohorts
cohorts = moodle_call(url, tok, "core_cohort_get_cohorts")

# cohort_members (estándar, sin timeadded)
cohort_members = []
for c in cohorts:
    r = moodle_call(url, tok, "core_cohort_get_cohort_members",
                    **{"cohortids[0]": c["id"]})
    for uid in r[0]["userids"]:
        cohort_members.append({"cohortid": c["id"], "userid": uid})

# cohort_members_ext (custom, CON timeadded) — REQUIERE plugin §9.8
cohort_members_ext = moodle_call(url, tok,
    "local_stratiorep_get_cohort_members")

# user_courses (N+1 por usuario)
user_courses = []
for u in users:
    r = moodle_call(url, tok, "core_enrol_get_users_courses",
                    userid=u["id"])
    for c in r:
        user_courses.append({"userid": u["id"], **c})

# user_grades (N+1 por (usuario, curso)) — MUY LENTO
# Usar custom local_stratiorep_get_all_grades si se implementa (recomendado)
user_grades = []
for u in users:
    for c in courses:
        r = moodle_call(url, tok, "gradereport_user_get_grade_items",
                        courseid=c["id"], userid=u["id"])
        # extraer items de r["usergrades"][0]["gradeitems"]
        ...

# course_completions (N+1 por (usuario, curso))
# Similar: candidato a reemplazar por custom.

# attendance_sessions (custom) — REQUIERE plugin §9.8
attendance_sessions = moodle_call(url, tok,
    "local_stratiorep_get_attendance_sessions")

# enrol_cohort_course (custom) — REQUIERE plugin §9.8
enrol_cohort_course = moodle_call(url, tok,
    "local_stratiorep_get_enrol_cohort_course")
```

### 8.2 Capa semántica (Spark SQL) — se ejecuta UNA vez

Las tablas raw se registran como externas sobre `/informes/moodle/{dataset}/`. El esquema de cada JSON de Moodle (ya convertido a Parquet) determina los nombres de columna.

#### `dim_partners.sql`
```sql
CREATE OR REPLACE TABLE semantic.dim_partners AS
WITH partners_from_users AS (
  SELECT DISTINCT
    CASE
      WHEN LOWER(email) LIKE '%stratio%' OR LOWER(username) LIKE '%stratio%' THEN 'stratio'
      ELSE reverse(split(reverse(username), '-')[0])
    END AS partner
  FROM raw.users
)
SELECT p.partner, m.tipo, m.region, m.trajo_oportunidades,
       m.trajo_clientes, m.paga_certificacion, m.total_pagado, m.notas
FROM partners_from_users p
LEFT JOIN raw.partners_meta m ON m.partner = p.partner;
```

#### `dim_cohortes.sql`
```sql
CREATE OR REPLACE TABLE semantic.dim_cohortes AS
SELECT
  id AS cohort_id,
  name AS cohort_name,
  CASE
    WHEN LOWER(name) LIKE '%governance%'      THEN 'Governance'
    WHEN LOWER(name) LIKE '%data processing%' THEN 'Data Processing'
    WHEN LOWER(name) LIKE '%intelligence%'    THEN 'Intelligence'
    WHEN LOWER(name) LIKE '%operaciones%'     THEN 'Operaciones'
    ELSE 'Otros'
  END AS categoria,
  NULLIF(regexp_extract(name, '(1[34]\\.[0-9])', 1), '') AS version,
  CASE
    WHEN name LIKE '% - ES' THEN 'ES'
    WHEN name LIKE '% - EN' THEN 'EN'
    WHEN name LIKE '% - FR' THEN 'FR'
    ELSE NULL
  END AS idioma,
  CAST(visible AS BOOLEAN) AS visible
FROM raw.cohorts;
```

#### `dim_cursos.sql`
```sql
CREATE OR REPLACE TABLE semantic.dim_cursos AS
SELECT
  id AS course_id,
  fullname AS course_name,
  (LOWER(fullname) LIKE '%certificación%' OR LOWER(fullname) LIKE '%certification%') AS es_certificacion,
  CASE
    WHEN LOWER(fullname) LIKE '%governance%'      THEN 'Governance'
    WHEN LOWER(fullname) LIKE '%data processing%' THEN 'Data Processing'
    WHEN LOWER(fullname) LIKE '%intelligence%'    THEN 'Intelligence'
    WHEN LOWER(fullname) LIKE '%operaciones%'     THEN 'Operaciones'
    ELSE 'Otros'
  END AS categoria,
  NULLIF(regexp_extract(fullname, '(1[34]\\.[0-9])', 1), '') AS version,
  CASE
    WHEN fullname LIKE '% - ES' THEN 'ES'
    WHEN fullname LIKE '% - EN' THEN 'EN'
    WHEN fullname LIKE '% - FR' THEN 'FR'
    ELSE NULL
  END AS idioma
FROM raw.courses;
```

#### `f_usuarios.sql`
La API de Moodle devuelve `timecreated` y `lastaccess` como Unix epoch.
```sql
CREATE OR REPLACE TABLE semantic.f_usuarios AS
SELECT
  u.id AS userid,
  u.username,
  u.email,
  concat(u.firstname, ' ', u.lastname) AS nombre_completo,
  CASE
    WHEN LOWER(u.email) LIKE '%stratio%' OR LOWER(u.username) LIKE '%stratio%' THEN 'stratio'
    ELSE reverse(split(reverse(u.username), '-')[0])
  END AS partner,
  from_unixtime(u.timecreated) AS fecha_alta,
  from_unixtime(u.lastaccess)  AS ultimo_acceso,
  (u.suspended = 0) AS activo
FROM raw.users u;
```

#### `f_inscripciones.sql`
```sql
CREATE OR REPLACE TABLE semantic.f_inscripciones AS
SELECT
  cm.userid,
  cm.cohortid AS cohort_id,
  fu.partner,
  dc.categoria,
  dc.version,
  from_unixtime(cm.timeadded) AS fecha_inscripcion,
  date_format(from_unixtime(cm.timeadded), 'yyyy-MM') AS mes_inscripcion
FROM raw.cohort_members_ext cm
JOIN semantic.f_usuarios   fu ON fu.userid = cm.userid
JOIN semantic.dim_cohortes dc ON dc.cohort_id = cm.cohortid;
```

#### `f_certificaciones.sql` ⭐
La forma de la tabla raw `user_grades` depende de cómo la serialicemos. Asumo que cada fila lleva `userid`, `courseid`, `itemname`, `gradeformatted` y `gradedatesubmitted` extraídos del JSON de `gradereport_user_get_grade_items`.
```sql
CREATE OR REPLACE TABLE semantic.f_certificaciones AS
SELECT
  g.userid,
  g.courseid AS course_id,
  fu.partner,
  CAST(g.graderaw AS DECIMAL(5,2)) AS finalgrade,
  (CAST(g.graderaw AS DECIMAL(5,2)) >= 70) AS aprobado,
  from_unixtime(g.gradedategraded) AS fecha_nota
FROM raw.user_grades g
JOIN semantic.dim_cursos dc ON dc.course_id = g.courseid
JOIN semantic.f_usuarios fu ON fu.userid = g.userid
WHERE g.itemtype = 'course'
  AND g.graderaw IS NOT NULL
  AND dc.es_certificacion = TRUE;
```

#### `f_actividad.sql`
```sql
CREATE OR REPLACE TABLE semantic.f_actividad AS
WITH sesiones AS (
  SELECT
    s.userid,
    s.courseid AS course_id,
    MIN(from_unixtime(s.login)) AS primer_acceso,
    MAX(from_unixtime(s.login)) AS ultimo_acceso
  FROM raw.attendance_sessions s
  GROUP BY s.userid, s.courseid
)
SELECT
  se.userid,
  se.course_id,
  fu.partner,
  TRUE AS tiene_actividad,
  se.primer_acceso,
  se.ultimo_acceso
FROM sesiones se
JOIN semantic.f_usuarios fu ON fu.userid = se.userid;
```

#### `f_dedicacion.sql`
```sql
CREATE OR REPLACE TABLE semantic.f_dedicacion AS
SELECT
  s.userid,
  s.courseid AS course_id,
  fu.partner,
  date_format(date_trunc('month', from_unixtime(s.login)), 'yyyy-MM') AS mes,
  ROUND(SUM(s.duration) / 3600.0, 2) AS horas
FROM raw.attendance_sessions s
JOIN semantic.f_usuarios fu ON fu.userid = s.userid
GROUP BY s.userid, s.courseid, fu.partner,
         date_trunc('month', from_unixtime(s.login));
```

### 8.3 Capa reporting (Spark SQL) — se ejecuta UNA vez

#### `r_resumen_partner.sql`
```sql
CREATE OR REPLACE TABLE reporting.r_resumen_partner AS
SELECT
  p.partner, p.tipo, p.region,
  COUNT(DISTINCT u.userid)                                 AS total_altas,
  COUNT(DISTINCT i.userid)                                 AS total_inscritos,
  COUNT(DISTINCT CASE WHEN c.aprobado THEN c.userid END)   AS total_certificados,
  COALESCE(SUM(d.horas), 0)                                AS total_horas,
  MAX(u.ultimo_acceso)                                     AS ultimo_acceso
FROM semantic.dim_partners p
LEFT JOIN semantic.f_usuarios        u ON u.partner = p.partner
LEFT JOIN semantic.f_inscripciones   i ON i.partner = p.partner
LEFT JOIN semantic.f_certificaciones c ON c.partner = p.partner
LEFT JOIN semantic.f_dedicacion      d ON d.partner = p.partner
GROUP BY p.partner, p.tipo, p.region;
```

#### `r_evolucion_mensual.sql`
```sql
CREATE OR REPLACE TABLE reporting.r_evolucion_mensual AS
WITH altas AS (
  SELECT partner, date_format(fecha_alta, 'yyyy-MM') AS mes, COUNT(*) AS altas
  FROM semantic.f_usuarios GROUP BY 1, 2
),
inscritos AS (
  SELECT partner, mes_inscripcion AS mes, COUNT(DISTINCT userid) AS inscritos
  FROM semantic.f_inscripciones GROUP BY 1, 2
),
certificados AS (
  SELECT partner, date_format(fecha_nota, 'yyyy-MM') AS mes,
         COUNT(DISTINCT CASE WHEN aprobado THEN userid END) AS certificados
  FROM semantic.f_certificaciones GROUP BY 1, 2
),
horas AS (
  SELECT partner, mes, SUM(horas) AS horas,
         COUNT(DISTINCT userid) AS usuarios_activos
  FROM semantic.f_dedicacion GROUP BY 1, 2
)
SELECT
  COALESCE(a.partner, i.partner, c.partner, h.partner) AS partner,
  COALESCE(a.mes, i.mes, c.mes, h.mes)                 AS mes,
  a.altas, i.inscritos, c.certificados, h.horas, h.usuarios_activos
FROM altas a
FULL OUTER JOIN inscritos    i USING (partner, mes)
FULL OUTER JOIN certificados c USING (partner, mes)
FULL OUTER JOIN horas        h USING (partner, mes)
ORDER BY partner, mes;
```

#### `r_partner_categoria.sql`
```sql
CREATE OR REPLACE TABLE reporting.r_partner_categoria AS
SELECT
  fu.partner, dc.categoria,
  COUNT(DISTINCT c.userid)                               AS alumnos,
  COUNT(DISTINCT CASE WHEN c.aprobado THEN c.userid END) AS aprobados
FROM semantic.f_certificaciones c
JOIN semantic.dim_cursos dc ON dc.course_id = c.course_id
JOIN semantic.f_usuarios fu ON fu.userid = c.userid
GROUP BY fu.partner, dc.categoria;
```

#### `r_partner_version.sql`
```sql
CREATE OR REPLACE TABLE reporting.r_partner_version AS
SELECT
  fu.partner, dc.version,
  COUNT(DISTINCT c.userid)                               AS alumnos,
  COUNT(DISTINCT CASE WHEN c.aprobado THEN c.userid END) AS aprobados
FROM semantic.f_certificaciones c
JOIN semantic.dim_cursos dc ON dc.course_id = c.course_id
JOIN semantic.f_usuarios fu ON fu.userid = c.userid
WHERE dc.version IS NOT NULL
GROUP BY fu.partner, dc.version;
```

#### `r_detalle_certificados.sql`
```sql
CREATE OR REPLACE TABLE reporting.r_detalle_certificados AS
SELECT
  u.userid, u.username, u.email, u.partner,
  dc.course_name, dc.categoria, dc.version, dc.idioma,
  c.finalgrade, c.aprobado, c.fecha_nota
FROM semantic.f_certificaciones c
JOIN semantic.f_usuarios u ON u.userid = c.userid
JOIN semantic.dim_cursos dc ON dc.course_id = c.course_id
WHERE c.aprobado = TRUE;
```

#### `r_alertas.sql`
```sql
CREATE OR REPLACE TABLE reporting.r_alertas AS
SELECT
  partner,
  MAX(ultimo_acceso) AS ultimo_acceso,
  DATEDIFF(CURRENT_DATE, CAST(MAX(ultimo_acceso) AS DATE)) AS dias_sin_actividad
FROM semantic.f_usuarios
GROUP BY partner
HAVING MAX(ultimo_acceso) < date_sub(CURRENT_DATE, 30);
```

---

## 9. El agente de automatización

### 9.1 Alcance

Solo capa RAW. Tres tareas:

1. **Extraer** cada dataset de §5.1 llamando a la API REST de Moodle.
2. **Cargar** a HDFS vía la API de Rocket (§9.6).
3. **Validar** cada dataset: row count esperado vs recibido, checksum, partición escrita correctamente.

Si algo falla, exit code ≠ 0 y log detallado con el dataset ofensor.

### 9.2 Flujo

```
main.py
  ├─ diagnóstico previo (opcional): check_moodle()
  ├─ for dataset in DATASETS:
  │   ├─ rows = extract.run(dataset)              # lista de dicts
  │   ├─ path = to_parquet.write(rows, dataset)   # Parquet local
  │   ├─ cs_local = checksum(path)
  │   ├─ upload_hdfs.put(path, dataset, ingest_date)
  │   ├─ rows_remote = upload_hdfs.count(dataset, ingest_date)
  │   └─ validate.assert_ok(len(rows), rows_remote, cs_local)
  └─ report.print_summary()
```

### 9.3 Variables de entorno (`.env.example`)

```env
# ─── Moodle (API REST) ───────────────────────────────────────────
MOODLE_URL=https://tu-moodle.stratio.com
MOODLE_TOKEN=                         # token con acceso a las funciones §9.7

# ─── Stratio (API Rocket para subir a HDFS) ──────────────────────
STRATIO_URL=https://api.int.stratio.com
STRATIO_TOKEN=                        # se obtiene con get_stratio_token.py
STRATIO_USER=
STRATIO_PASS=
STRATIO_TENANT=formacion

# ─── HDFS ────────────────────────────────────────────────────────
HDFS_BASE_PATH=/informes/moodle

# ─── Agente ──────────────────────────────────────────────────────
AGENT_WORKDIR=/tmp/moodle-reports-agent
AGENT_LOG_LEVEL=INFO
```

### 9.4 Validación

- **Row counts:** longitud de la lista en memoria antes de serializar vs filas del Parquet tras subirlo.
- **Checksums:** SHA-256 del Parquet local antes de subir; tras subir, comparar con el tamaño/hash que devuelva la API de Rocket (si lo expone).
- **Tolerancia:** cero. Cualquier discrepancia aborta esa carga pero NO borra la partición anterior.

### 9.5 Limpieza del snapshot anterior

Tras ingesta satisfactoria de TODOS los datasets, borrar `ingest_date` anterior. Si algo falla, la anterior se mantiene intacta.

### 9.6 Subida a HDFS vía API de Rocket

Base URL: `https://admin.practices.stratio.com`  
Prefijo de todos los endpoints: `/rocketf/fileBrowser/`  
Filesystem fijo: `{"id": "hdfs.formacion-datastores", "type": "HDFS"}`

**Autenticación:** cookies en cada request (no Bearer token):
- `stratio-cookie` — JWT Stratio con `tenant: "formacion"` (obtenido con `get_practices_cookies.py` de `training-agents`)
- `JSESSIONID` — sesión del servidor Rocket
- `stickyrocket` — sticky session del balanceador (opcional pero recomendable)

**La subida es un proceso de 2 pasos:**

**Paso 1 — Subir binario al tmp de Rocket**
```
POST /rocketf/fileBrowser/uploadLocalFile
Content-Type: multipart/form-data; boundary=...

--{boundary}
Content-Disposition: form-data; name="binary"; filename="{filename}"
Content-Type: application/octet-stream

<bytes del fichero>
--{boundary}--
```
Respuesta: `dockerPath` del fichero en el tmp del contenedor Rocket (ej: `/tmp/uploads/{uuid}/{filename}`).

**Paso 2 — Mover del tmp de Rocket al path HDFS**
```
POST /rocketf/fileBrowser/putLocalFileToHdfs
Content-Type: application/json

{
  "pathHdfs":        "/informes/moodle/users/ingest_date=2026-04-21",
  "dockerPath":      "/tmp/uploads/{uuid}/{filename}",
  "targetFilesystem": {"id": "hdfs.formacion-datastores", "type": "HDFS"}
}
```
El directorio `pathHdfs` se crea en HDFS si no existe.

**Listar directorio HDFS**
```
POST /rocketf/fileBrowser/findByPath
Content-Type: application/json

{"pathHdfs": "/informes/moodle", "targetFilesystem": {"id": "hdfs.formacion-datastores", "type": "HDFS"}}
```
Respuesta: array JSON directo (sin wrapper). Campos confirmados por HAR:
`name` (ruta completa), `type` (`file`/`directory`), `size`, `owner`, `group`, `permissions`, `lastUpdated` (unix ms).

**Obtener filesystems disponibles**
```
GET /rocketf/fileBrowser/getFilesystems
```
Respuesta: lista de `{"id": "...", "type": "HDFS"}`.

**Borrar items**
```
DELETE /rocketf/fileBrowser/delete
Content-Type: application/json

{"files":[{"path":"/formacion/practica_cama.csv"}],"targetFilesystem":{"id":"hdfs.formacion-datastores","type":"HDFS"}}
```
Respuesta: `"OK"` (text/plain, HTTP 200). Acepta múltiples paths en el array `files`.

**Notas de validación (§9.4):**  
La API de Rocket no expone row count de Parquet. La validación se hace comparando el row count local (antes de serializar) con el row count del Parquet leído de nuevo tras escritura local, antes de subir. Tras la subida, se verifica que el fichero aparece en `findByPath` con `size > 0`.

### 9.7 Funciones Moodle estándar necesarias

Las funciones marcadas ✅ están disponibles en el token. Las marcadas 🔄 han sido **reemplazadas por funciones del plugin** `local_stratiorep` y ya no son necesarias en el token.

| Función | Para qué | Estado |
|---|---|---|
| `core_webservice_get_site_info` | Diagnóstico / verificar token | ✅ |
| `core_user_get_users` | Listado masivo de usuarios | 🔄 reemplazada por `local_stratiorep_get_users` |
| `core_user_get_users_by_field` | Buscar usuario concreto (fallback) | ✅ |
| `core_course_get_courses` | Listado de cursos | ✅ |
| `core_cohort_get_cohorts` | Listado de cohortes con nombres | ✅ (disponible en token) |
| `core_cohort_get_cohort_members` | Miembros de cohorte (sin fecha de alta) | 🔄 reemplazada por `local_stratiorep_get_cohort_members` |
| `core_enrol_get_users_courses` | Inscripciones de un usuario (fallback N+1) | 🔄 reemplazada por `local_stratiorep_get_user_enrollments` |
| `gradereport_user_get_grade_items` | Notas por usuario/curso (fallback N+1) | 🔄 reemplazada por `local_stratiorep_get_all_grades` |
| `core_completion_get_course_completion_status` | Completion por usuario/curso (fallback N+1) | 🔄 reemplazada por `local_stratiorep_get_course_completions` |

> Las funciones 🔄 siguen como fallback en el código (`extract.py`) por si el plugin dejase de estar disponible, pero en condiciones normales nunca se llaman.

### 9.8 Funciones Moodle custom (plugin `local_stratiorep`) — ✅ INSTALADO Y OPERATIVO

El plugin está instalado en el servidor. Todas las funciones están implementadas en `moodle_plugin/externallib.php` y definidas en `moodle_plugin/db/services.php`.

| Función | SQL equivalente | Motivo | Estado |
|---|---|---|---|
| `local_stratiorep_get_cohort_members` | `SELECT CONCAT(cohortid,'_',userid) AS recid, cohortid, userid, timeadded FROM mdl_cohort_members` | `core_cohort_get_cohort_members` no devuelve `timeadded` | ✅ |
| `local_stratiorep_get_attendance_sessions` | `SELECT s.userid, r.course AS courseid, s.login, s.duration FROM mdl_attendanceregister_session s JOIN mdl_attendanceregister r ON r.id=s.register` | Plugin `attendanceregister` no expone webservices | ✅ |
| `local_stratiorep_get_enrol_cohort_course` | `SELECT customint1 AS cohortid, courseid FROM mdl_enrol WHERE enrol='cohort'` | Puente cohorte→curso no expuesto en la API estándar | ✅ |
| `local_stratiorep_get_all_grades` | `SELECT gg.userid, gi.courseid, gg.finalgrade AS graderaw, gg.timemodified AS gradedategraded FROM mdl_grade_grades gg JOIN mdl_grade_items gi ON gi.id=gg.itemid WHERE gi.itemtype='course' AND gg.finalgrade IS NOT NULL` | Evita N+1 (~4000 llamadas) en notas; una sola llamada trae todo | ✅ |
| `local_stratiorep_get_users` | `SELECT id, username, email, firstname, lastname, timecreated, lastaccess, suspended FROM mdl_user WHERE deleted=0 AND id>1` | Extracción ligera de usuarios en una sola llamada | ✅ |
| `local_stratiorep_get_user_enrollments` | `SELECT CONCAT(ue.userid,'_',e.courseid) AS id, ue.userid, e.courseid FROM mdl_user_enrolments ue JOIN mdl_enrol e ON e.id=ue.enrolid WHERE ue.status=0 AND e.status=0` | Reemplaza N+1 de inscripciones; una sola llamada | ✅ |
| `local_stratiorep_get_course_completions` | `SELECT id, userid, course AS courseid, CASE WHEN timecompleted>0 THEN 1 ELSE 0 END AS completed, timecompleted FROM mdl_course_completions` | Reemplaza N+1 de completions; una sola llamada | ✅ |

> **Nota importante — `get_cohort_members`:** `$DB->get_records_sql()` indexa por la primera columna. Se usa `CONCAT(cohortid,'_',userid) AS recid` como primera columna para evitar que filas con el mismo `cohortid` se sobreescriban (bug crítico que colapsaba 33.549 filas a 49).

**Esqueleto del plugin** (`moodle_plugin/`):

```
moodle_plugin/
├── version.php
├── db/
│   ├── services.php          # define las funciones
│   └── access.php            # permisos mínimos
└── externallib.php           # implementación
```

`db/services.php`:
```php
<?php
$functions = [
  'local_stratiorep_get_cohort_members' => [
    'classname'   => 'local_stratiorep_external',
    'methodname'  => 'get_cohort_members',
    'description' => 'Devuelve mdl_cohort_members con timeadded',
    'type'        => 'read',
    'capabilities'=> '',
  ],
  'local_stratiorep_get_attendance_sessions' => [...],
  'local_stratiorep_get_enrol_cohort_course' => [...],
  'local_stratiorep_get_all_grades'          => [...],
];
$services = [
  'Stratio Reports' => [
    'functions' => array_keys($functions),
    'restrictedusers' => 1,
    'enabled' => 1,
    'shortname' => 'stratiorep',
  ],
];
```

`externallib.php` (esqueleto de una función):
```php
public static function get_cohort_members() {
    global $DB;
    $rows = $DB->get_records_sql(
        "SELECT cohortid, userid, timeadded FROM {cohort_members}"
    );
    return array_values((array) $rows);
}

public static function get_cohort_members_returns() {
    return new external_multiple_structure(
        new external_single_structure([
            'cohortid'  => new external_value(PARAM_INT),
            'userid'    => new external_value(PARAM_INT),
            'timeadded' => new external_value(PARAM_INT),
        ])
    );
}
```

El plugin se instala en el Moodle de formación por el equipo que administre la plataforma. Hasta entonces, los datasets `cohort_members_ext`, `attendance_sessions` y `enrol_cohort_course` no podrán extraerse y las tablas/KPIs que dependen de ellos quedan sin datos (se verá como valores vacíos en el dashboard, no romperá el pipeline).

### 9.9 Diagnóstico previo

Copiar `diagnostico_moodle.py` de `training-agents` y adaptar la lista `FUNCIONES_NECESARIAS` con las de §9.7 y §9.8. Se ejecuta antes del primer despliegue y cuando algo falla:

```bash
python3 src/diagnostico/diagnostico_moodle.py
```

Comprueba:
- `MOODLE_URL` y `MOODLE_TOKEN` en `.env`.
- Conectividad y validez del token (`core_webservice_get_site_info`).
- Cada función de §9.7 y §9.8 responde (no da `accessexception`).

---

## 10. Convenciones

- **Idioma:** identificadores técnicos en inglés, comentarios en castellano.
- **Formato fecha:** `YYYY-MM-DD` (particiones), `YYYY-MM` (agregados mensuales).
- **Nulos:** explícitos.
- **Aprobado de certificación:** `finalgrade >= 70`, centralizado en `f_certificaciones`.
- **Curso "certificación":** `course_name` contiene `certificación` o `certification` (case-insensitive), centralizado en `dim_cursos.es_certificacion`.
- **Código del agente:** Python 3.11+, **solo stdlib** (`urllib`, `json`) + `pyarrow` para Parquet. Sin `requests`, sin `pandas`. Misma convención que `training-agents`.
- **Nombres de dataset (HDFS):** lo que devuelve la función de Moodle, simplificado. No `mdl_*` (ya no es SQL). Ej: `users`, `cohort_members_ext`, `attendance_sessions`.
- **Particionado HDFS:** `ingest_date=YYYY-MM-DD` en todas las tablas raw de Moodle. `partners_meta` sin partición.
- **SQL:** Spark SQL para semántica y reporting. Nombres `snake_case`. Un fichero `.sql` por dataset.
- **Versionado:** todo en git. Cambios de esquema registrados en `docs/data_dictionary.md`.

---

## 11. Decisiones tomadas

| # | Tema | Decisión | Fecha |
|---|---|---|---|
| 1 | Umbral de aprobado (certificaciones) | `finalgrade >= 70` | 2026-04-21 |
| 2 | Criterio de "curso finalizado" (cursos NO certificación) | Aplazado: de momento solo marcar si tiene actividad | 2026-04-21 |
| 3 | Alcance del agente | Extraer + subir a HDFS + validar | 2026-04-21 |
| 4 | Motor de la capa semántica | Spark SQL sobre HDFS | 2026-04-21 |
| 5 | Frecuencia de ingesta RAW | Diaria, full-snapshot | 2026-04-21 |
| 6 | `partners_meta` | Tabla maestra subida una vez; gestión avanzada = futura | 2026-04-21 |
| 7 | Aprobación | Solo aplica a certificaciones; cohorte pasa a ser solo descriptiva | 2026-04-21 |
| 8 | Histórico | Solo último snapshot; time travel = futuro | 2026-04-21 |
| 9 | Construcción de semántica y reporting | Una sola vez sobre Stratio; vive en el repo pero no se refresca a diario | 2026-04-21 |
| 10 | Acceso a Moodle | **API REST con `wstoken`** (no conexión directa a PostgreSQL) | 2026-04-21 |
| 11 | Estrategia de extracción | **Opción C**: API REST estándar + funciones custom en plugin `local_stratiorep` para lo que no cubre la API | 2026-04-21 |
| 12 | Token Moodle | Reutilizar el del corrector (ya tiene `mod_assign_*`, `core_user_*`, `core_course_*`); añadir funciones de §9.7 y §9.8 al mismo servicio | 2026-04-21 |
| 13 | Convención de código | Stdlib (`urllib`, `json`) + `pyarrow`; sin `requests`/`pandas`. Misma convención que `training-agents` | 2026-04-21 |
| 14 | Subida HDFS | Vía API de Rocket (detalles exactos pendientes de recibir — §9.6) | 2026-04-21 |
| 15 | Tenant Stratio | `formacion` | 2026-04-21 |
| 16 | Funciones estándar Moodle | No se añaden al token: sustituidas por equivalentes custom en `local_stratiorep` más eficientes (una sola llamada vs N+1). Solo `core_cohort_get_cohorts` se usa directamente (ya disponible en el token). | 2026-04-22 |
| 17 | Validación local pre-Stratio | `src/local_validate.py` ejecuta la capa semántica + reporting en DuckDB sobre los Parquet locales y exporta Excel. Permite validar KPIs contra el Google Sheet antes de subir a HDFS. | 2026-04-22 |

---

## 12. Roadmap

### Fase 1 — Agente RAW *(semana 1-2)* ✅ COMPLETADA
- [x] Crear repo con la estructura de §4.
- [x] Copiar `shared/utils.py` (cargador .env, log) de `training-agents`.
- [x] Copiar/adaptar `moodle/moodle_api.py::_moodle_call` → `src/shared/moodle_api.py`.
- [x] Implementar `src/agent/extract.py` con una función por dataset de §5.1.
- [x] Serializar a Parquet con `pyarrow` (`src/agent/to_parquet.py`).
- [x] Adaptar `diagnostico_moodle.py` con la lista completa de funciones.
- [x] Implementar `src/agent/upload_hdfs.py` con las llamadas a la API de Rocket.
- [x] Implementar validación (row counts + checksums).
- [x] Tests de la regla del partner y de paginación (18/18 ✓).
- [x] `src/shared/practices_auth.py` — renovación de cookies autónoma (sin dependencia de training-agents).

### Fase 1.5 — Plugin Moodle custom *(paralelo a Fase 1)* ✅ COMPLETADA
- [x] Plugin `local_stratiorep` instalado en el servidor (verificado por diagnóstico).
- [x] 7 funciones implementadas: `get_cohort_members`, `get_attendance_sessions`, `get_enrol_cohort_course`, `get_all_grades`, `get_users`, `get_user_enrollments`, `get_course_completions`.
- [x] Las 3 funciones estándar "pendientes" (`core_user_get_users`, `core_cohort_get_cohort_members`, `core_enrol_get_users_courses`) ya no son necesarias en el token: sustituidas por equivalentes custom más eficientes.
- [x] Extracción completa probada localmente: 10 datasets, todos correctos (4.252 usuarios, 49 cohortes, 33.549 inscripciones, 5.383 notas, 237.515 sesiones de asistencia).
- [x] Primer snapshot local generado con `--skip-upload`. Subida a HDFS pendiente (requiere cookies Rocket).

### Fase 2 — Capa semántica *(ejecución única sobre Stratio)*
- [x] Escribir los SQL de §8.2 en `src/transform/semantic/` (8 ficheros).
- [x] Validación local completa con DuckDB (`src/local_validate.py`) — KPIs verificados contra el Google Sheet original.
- [ ] **BLOQUEADO:** Entender cómo se ejecutan los SQL en Stratio (mecanismo distinto al Spark SQL estándar). Pendiente de recibir ficheros de ejemplo del entorno Stratio para adaptar `src/deploy/run_transforms.py` o el mecanismo que corresponda.
- [ ] Registrar tablas externas sobre `/informes/moodle/{dataset}/` en Stratio.
- [ ] Ejecutar los 8 `CREATE OR REPLACE TABLE` semánticos.
- [ ] Spot-check de 3-5 partners contra el Excel local generado por `local_validate.py`.

### Fase 3 — Capa reporting + Metabase *(ejecución única)*
- [x] Escribir los SQL de §8.3 en `src/transform/reporting/` (6 ficheros).
- [ ] Ejecutar los 6 `CREATE OR REPLACE TABLE` de reporting (mismo mecanismo que Fase 2).
- [ ] **Metabase — automatización parcial:** crear las cards/preguntas vía API REST de Metabase (script Python); el layout visual del dashboard se monta a mano en la UI. Pendiente de conocer URL y versión de Metabase.

### Fase 4 — Producción
- [ ] Primer snapshot real subido a HDFS: `python3 src/refresh_cookies.py && python3 -m src.agent.main`.
- [ ] Agente en cron diario.
- [ ] Refresco opcional de `semantic.*` y `reporting.*` tras ingesta OK.
- [ ] Monitorización básica (logs; notificación si hace falta).

---

## 13. Estado actual

- [x] Consultas legacy inventariadas en `sql_legacy/consultas_informe_alberto.txt`.
- [x] Google Sheet analizado: 21 bloques mapeados (§7).
- [x] Decisiones cerradas (§11).
- [x] Estrategia Moodle definida: API REST + plugin custom (§11 decisión 11).
- [x] Repo creado (estructura de directorios creada 2026-04-21).
- [x] Llamadas exactas a la API de Rocket recibidas y documentadas (§9.6). Endpoint de borrado confirmado.
- [x] `src/shared/utils.py` — cargador .env y log.
- [x] `src/shared/moodle_api.py` — _moodle_call + funciones por dataset (estándar y custom).
- [x] `src/agent/config.py` — carga .env, constantes, lista de datasets.
- [x] `src/agent/extract.py` — orquestador con caché de datasets base; fallback N+1 → custom.
- [x] `src/agent/upload_hdfs.py` — subida/listado/borrado en HDFS vía Rocket.
- [x] `src/diagnostico/diagnostico_moodle.py` — check previo de funciones §9.7 y §9.8.
- [x] `src/agent/to_parquet.py` — serialización JSON → Parquet (pyarrow, snappy).
- [x] `src/agent/validate.py` — row counts pre/post serialización + checksum SHA-256 + verificación HDFS.
- [x] `src/agent/sanity.py` — validación de negocio con DuckDB: partners, categorías, versiones, certificaciones, alertas.
- [x] `src/agent/main.py` — punto de entrada: extrae → serializa → valida → sanity → sube → limpia → resumen.
- [x] `src/shared/practices_auth.py` — login OAuth2-proxy Rocket vía stdlib (urllib + http.cookiejar) + fallback Selenium.
- [x] `src/refresh_cookies.py` — renovación de cookies de Rocket en .env (sin dependencia de training-agents).
- [x] `src/transform/semantic/` — SQL Spark para dim_partners, dim_cohortes, dim_cursos, f_usuarios, f_inscripciones, f_certificaciones, f_actividad, f_dedicacion.
- [x] `src/transform/reporting/` — SQL Spark para r_resumen_partner, r_evolucion_mensual, r_partner_categoria, r_partner_version, r_detalle_certificados, r_alertas.
- [x] `tests/test_partner_rule.py` — 11 tests regla canónica de partner (18/18 ✓).
- [x] `tests/test_pagination.py` — 7 tests lógica de paginación Moodle (18/18 ✓).
- [x] Plugin Moodle custom `local_stratiorep` instalado y operativo — 7 funciones (ver §9.8).
- [x] Extracción completa probada localmente (`--skip-upload`). KPIs verificados: 149 partners, 4.252 usuarios, 2.499 certificaciones aprobadas, 49.276 horas.
- [x] `src/local_validate.py` — validación local de la capa semántica + reporting completa en DuckDB; exporta Excel con 6 hojas (`resumen_partner`, `evolucion_mensual`, `partner_categoria`, `partner_version`, `detalle_certificados`, `alertas`). Soporta `--partner` para informes individuales.
- [x] `src/data/partners_meta.csv` — metadatos de negocio (tipo, región, oportunidades, clientes, certificación, pagado) integrados desde el Google Sheet original.
- [ ] **SIGUIENTE:** Primer snapshot RAW subido a HDFS — ejecutar `python3 src/refresh_cookies.py` y luego `python3 -m src.agent.main`.
- [ ] Capa semántica ejecutada sobre Stratio (una vez con datos reales).
- [ ] Dashboard Metabase publicado.

---

## 14. Glosario

- **Partner:** organización que usa Stratio. Se extrae del username (último token tras el último `-`). Excepción: emails/usernames con `stratio` → partner `stratio`.
- **Cohorte:** grupo de usuarios en Moodle. Agrupador descriptivo (categoría, versión, idioma), **no grano de aprobación**.
- **Categoría:** Governance, Data Processing, Intelligence, Operaciones, Otros.
- **Versión:** versión de Stratio referenciada en el nombre (13.0, 13.2, 14.0, 14.1, 14.6, 14.8).
- **Curso certificación:** curso cuyo `fullname` contiene `certificación` o `certification`.
- **Aprobado:** aplica solo a certificaciones; `finalgrade >= 70`.
- **Con actividad:** usuario con al menos una sesión registrada en `attendance_sessions` para ese curso.
- **Activo:** usuario Moodle no suspendido (`suspended=0`; nota: `deleted` no lo exponemos porque la API ya filtra borrados).
- **Full-snapshot:** cada ingesta trae la tabla completa, no incremental.
- **Funciones custom:** las que viven en el plugin `local_stratiorep` (§9.8), prefijadas con ese namespace.
- **Tenant:** `formacion` en Stratio (ver `STRATIO_TENANT`).
