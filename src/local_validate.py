"""
local_validate.py — Capa semántica + reporting en local con DuckDB.

Lee los Parquet del último snapshot, construye la capa semántica en DuckDB
y exporta todas las tablas de reporting a un único fichero Excel (una hoja por tabla).

Uso:
  python3 src/local_validate.py
  python3 src/local_validate.py --workdir /tmp/moodle-reports-agent/2026-04-22
  python3 src/local_validate.py --output /tmp/reports_local/informe.xlsx
"""

import argparse
import os
import sys
from datetime import date
from pathlib import Path

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, "src"))

try:
    import duckdb
except ImportError:
    print("Necesitas duckdb: pip install duckdb")
    sys.exit(1)

try:
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.utils import get_column_letter
except ImportError:
    print("Necesitas openpyxl: pip install openpyxl")
    sys.exit(1)

OK   = "\033[92m✓\033[0m"
FAIL = "\033[91m✗\033[0m"
WARN = "\033[93m⚠\033[0m"
INFO = "\033[94m·\033[0m"
SEP  = "─" * 56

PARTNER_RULE = """
  CASE
    WHEN LOWER(email)    LIKE '%stratio%'
      OR LOWER(username) LIKE '%stratio%' THEN 'stratio'
    ELSE reverse(string_split(reverse(username), '-')[1])
  END
"""

COHORT_CAT = """
  CASE
    WHEN LOWER(name) LIKE '%governance%'      THEN 'Governance'
    WHEN LOWER(name) LIKE '%data processing%' THEN 'Data Processing'
    WHEN LOWER(name) LIKE '%intelligence%'    THEN 'Intelligence'
    WHEN LOWER(name) LIKE '%operaciones%'     THEN 'Operaciones'
    ELSE 'Otros'
  END
"""

COURSE_CAT = """
  CASE
    WHEN LOWER(fullname) LIKE '%governance%'      THEN 'Governance'
    WHEN LOWER(fullname) LIKE '%data processing%' THEN 'Data Processing'
    WHEN LOWER(fullname) LIKE '%intelligence%'    THEN 'Intelligence'
    WHEN LOWER(fullname) LIKE '%operaciones%'     THEN 'Operaciones'
    ELSE 'Otros'
  END
"""


def latest_workdir() -> Path | None:
    base = Path("/tmp/moodle-reports-agent")
    if not base.exists():
        return None
    dirs = sorted([d for d in base.iterdir() if d.is_dir()], reverse=True)
    return dirs[0] if dirs else None


def find_parquet(workdir: Path, dataset: str) -> str | None:
    for f in workdir.glob(f"{dataset}*.parquet"):
        return str(f)
    return None


PARTNERS_META_CSV = os.path.join(
    os.path.abspath(os.path.join(os.path.dirname(__file__))), "data", "partners_meta.csv"
)


def _load_partners_meta(con: duckdb.DuckDBPyConnection) -> bool:
    """Registra partners_meta.csv como vista en DuckDB. Devuelve True si existe."""
    if not os.path.exists(PARTNERS_META_CSV):
        return False
    con.execute(
        f"CREATE OR REPLACE VIEW raw_partners_meta AS "
        f"SELECT * FROM read_csv('{PARTNERS_META_CSV}', header=true, "
        f"columns={{"
        f"'partner': 'VARCHAR', 'tipo': 'VARCHAR', 'region': 'VARCHAR', "
        f"'trajo_oportunidades': 'VARCHAR', 'trajo_clientes': 'VARCHAR', "
        f"'paga_certificacion': 'VARCHAR', 'total_pagado': 'VARCHAR'"
        f"}})"
    )
    return True


def build_semantic(con: duckdb.DuckDBPyConnection, workdir: Path) -> set[str]:
    """Crea las tablas semánticas en DuckDB. Devuelve el set de tablas creadas."""
    created = set()

    datasets = [
        "users", "courses", "cohorts", "cohort_members", "user_courses",
        "user_grades", "course_completions", "cohort_members_ext",
        "attendance_sessions", "enrol_cohort_course",
    ]
    for ds in datasets:
        path = find_parquet(workdir, ds)
        if path:
            con.execute(f"CREATE OR REPLACE VIEW raw_{ds} AS SELECT * FROM read_parquet('{path}')")

    has_meta = _load_partners_meta(con)

    if has_meta:
        con.execute(f"""
        CREATE OR REPLACE TABLE dim_partners AS
        WITH p AS (
          SELECT DISTINCT {PARTNER_RULE} AS partner
          FROM raw_users
        )
        SELECT
          p.partner,
          m.tipo,
          m.region,
          CASE WHEN m.trajo_oportunidades = 'true' THEN TRUE
               WHEN m.trajo_oportunidades = 'false' THEN FALSE
               ELSE NULL END AS trajo_oportunidades,
          CASE WHEN m.trajo_clientes = 'true' THEN TRUE
               WHEN m.trajo_clientes = 'false' THEN FALSE
               ELSE NULL END AS trajo_clientes,
          CASE WHEN m.paga_certificacion = 'true' THEN TRUE
               ELSE FALSE END AS paga_certificacion,
          TRY_CAST(NULLIF(m.total_pagado, '') AS DOUBLE) AS total_pagado
        FROM p
        LEFT JOIN raw_partners_meta m ON m.partner = p.partner
        """)
    else:
        con.execute(f"""
        CREATE OR REPLACE TABLE dim_partners AS
        SELECT DISTINCT {PARTNER_RULE} AS partner,
               NULL::VARCHAR AS tipo,
               NULL::VARCHAR AS region,
               NULL::BOOLEAN AS trajo_oportunidades,
               NULL::BOOLEAN AS trajo_clientes,
               FALSE         AS paga_certificacion,
               NULL::DOUBLE  AS total_pagado
        FROM raw_users
        """)
    created.add("dim_partners")

    con.execute(f"""
    CREATE OR REPLACE TABLE dim_cohortes AS
    SELECT
      id          AS cohort_id,
      name        AS cohort_name,
      {COHORT_CAT} AS categoria,
      NULLIF(regexp_extract(name, '(1[34]\\.[0-9])', 1), '') AS version,
      CASE
        WHEN name LIKE '% - ES' THEN 'ES'
        WHEN name LIKE '% - EN' THEN 'EN'
        WHEN name LIKE '% - FR' THEN 'FR'
        ELSE NULL
      END AS idioma,
      CAST(visible AS BOOLEAN) AS visible
    FROM raw_cohorts
    """)
    created.add("dim_cohortes")

    con.execute(f"""
    CREATE OR REPLACE TABLE dim_cursos AS
    SELECT
      id       AS course_id,
      fullname AS course_name,
      (LOWER(fullname) LIKE '%certificación%' OR LOWER(fullname) LIKE '%certification%')
               AS es_certificacion,
      {COURSE_CAT} AS categoria,
      NULLIF(regexp_extract(fullname, '(1[34]\\.[0-9])', 1), '') AS version,
      CASE
        WHEN fullname LIKE '% - ES' THEN 'ES'
        WHEN fullname LIKE '% - EN' THEN 'EN'
        WHEN fullname LIKE '% - FR' THEN 'FR'
        ELSE NULL
      END AS idioma
    FROM raw_courses
    """)
    created.add("dim_cursos")

    con.execute(f"""
    CREATE OR REPLACE TABLE f_usuarios AS
    SELECT
      u.id        AS userid,
      u.username,
      u.email,
      u.firstname || ' ' || u.lastname AS nombre_completo,
      {PARTNER_RULE} AS partner,
      to_timestamp(u.timecreated) AS fecha_alta,
      to_timestamp(u.lastaccess)  AS ultimo_acceso,
      (u.suspended = 0) AS activo
    FROM raw_users u
    """)
    created.add("f_usuarios")

    if find_parquet(workdir, "cohort_members_ext"):
        con.execute("""
        CREATE OR REPLACE TABLE f_inscripciones AS
        SELECT
          cm.userid,
          cm.cohortid   AS cohort_id,
          fu.partner,
          dc.categoria,
          dc.version,
          to_timestamp(cm.timeadded)                    AS fecha_inscripcion,
          strftime(to_timestamp(cm.timeadded), '%Y-%m') AS mes_inscripcion
        FROM raw_cohort_members_ext cm
        JOIN f_usuarios   fu ON fu.userid    = cm.userid
        JOIN dim_cohortes dc ON dc.cohort_id = cm.cohortid
        """)
        created.add("f_inscripciones")

    if find_parquet(workdir, "user_grades"):
        con.execute("""
        CREATE OR REPLACE TABLE f_certificaciones AS
        SELECT
          g.userid,
          g.courseid                      AS course_id,
          fu.partner,
          CAST(g.graderaw AS DOUBLE)      AS finalgrade,
          (CAST(g.graderaw AS DOUBLE) >= 70) AS aprobado,
          to_timestamp(g.gradedategraded) AS fecha_nota
        FROM raw_user_grades g
        JOIN dim_cursos  dc ON dc.course_id = g.courseid
        JOIN f_usuarios  fu ON fu.userid    = g.userid
        WHERE g.graderaw IS NOT NULL
          AND dc.es_certificacion = TRUE
        """)
        created.add("f_certificaciones")

    if find_parquet(workdir, "attendance_sessions"):
        con.execute("""
        CREATE OR REPLACE TABLE f_actividad AS
        WITH sesiones AS (
          SELECT s.userid, s.courseid AS course_id,
            MIN(to_timestamp(s.login)) AS primer_acceso,
            MAX(to_timestamp(s.login)) AS ultimo_acceso
          FROM raw_attendance_sessions s
          GROUP BY s.userid, s.courseid
        )
        SELECT se.userid, se.course_id, fu.partner,
               TRUE AS tiene_actividad,
               se.primer_acceso, se.ultimo_acceso
        FROM sesiones se
        JOIN f_usuarios fu ON fu.userid = se.userid
        """)
        created.add("f_actividad")

        con.execute("""
        CREATE OR REPLACE TABLE f_dedicacion AS
        SELECT
          s.userid, s.courseid AS course_id, fu.partner,
          strftime(date_trunc('month', to_timestamp(s.login)), '%Y-%m') AS mes,
          ROUND(SUM(s.duration) / 3600.0, 2) AS horas
        FROM raw_attendance_sessions s
        JOIN f_usuarios fu ON fu.userid = s.userid
        GROUP BY s.userid, s.courseid, fu.partner,
                 date_trunc('month', to_timestamp(s.login))
        """)
        created.add("f_dedicacion")

    return created


# ── Definición de tablas de reporting ─────────────────────────────────────────

def reporting_queries(semantic_tables: set[str], con) -> list[tuple[str, str, str]]:
    """Devuelve [(nombre_hoja, nombre_tabla, sql), ...]"""

    has_inscr  = "f_inscripciones"   in semantic_tables
    has_cert   = "f_certificaciones" in semantic_tables
    has_dedic  = "f_dedicacion"      in semantic_tables

    # Detectar años disponibles para el pivot dinámico
    years_altas = [r[0] for r in con.execute(
        "SELECT DISTINCT strftime(fecha_alta, '%Y') AS yr "
        "FROM f_usuarios WHERE fecha_alta IS NOT NULL ORDER BY 1"
    ).fetchall()]
    years_horas = [r[0] for r in con.execute(
        "SELECT DISTINCT LEFT(mes, 4) FROM f_dedicacion ORDER BY 1"
    ).fetchall()] if has_dedic else []

    altas_yr_cols  = "\n             ".join(
        f", count(DISTINCT CASE WHEN strftime(fecha_alta, '%Y') = '{y}' THEN userid END) AS altas_{y}"
        for y in years_altas
    )
    horas_yr_cols  = "\n             ".join(
        f", ROUND(SUM(CASE WHEN LEFT(mes, 4) = '{y}' THEN horas ELSE 0 END), 2) AS horas_{y}"
        for y in years_horas
    )
    altas_yr_sel   = "\n      ".join(f"base.altas_{y}," for y in years_altas)
    horas_yr_sel   = "\n      ".join(f"COALESCE(ded.horas_{y}, 0) AS horas_{y}," for y in years_horas)

    tables = []

    # ── r_resumen_partner ──────────────────────────────────────────────────────
    order = "total_certificados" if has_cert else "total_altas"

    sql_resumen = f"""
    WITH base AS (
      SELECT partner,
             count(DISTINCT userid) AS total_altas
             {altas_yr_cols},
             MAX(ultimo_acceso)     AS ultimo_acceso
      FROM f_usuarios GROUP BY partner
    )
    {"," + chr(10) + "    cert AS (SELECT partner, count(DISTINCT CASE WHEN aprobado THEN userid END) AS total_certificados FROM f_certificaciones GROUP BY partner)" if has_cert else ""}
    {"," + chr(10) + "    ded  AS (SELECT partner, ROUND(SUM(horas), 2) AS total_horas " + horas_yr_cols + " FROM f_dedicacion GROUP BY partner)" if has_dedic else ""}
    {"," + chr(10) + "    ins  AS (SELECT fu2.partner, count(DISTINCT cm.userid) AS total_inscritos FROM raw_cohort_members_ext cm JOIN f_usuarios fu2 ON fu2.userid = cm.userid GROUP BY fu2.partner)" if has_inscr else ""}
    SELECT
      base.partner,
      dp.tipo,
      dp.region,
      dp.trajo_oportunidades,
      dp.trajo_clientes,
      dp.paga_certificacion,
      dp.total_pagado,
      base.total_altas,
      {altas_yr_sel}
      {"COALESCE(ins.total_inscritos, 0)      AS total_inscritos," if has_inscr else ""}
      {"COALESCE(cert.total_certificados, 0)  AS total_certificados," if has_cert else ""}
      {"COALESCE(ded.total_horas, 0)          AS total_horas," if has_dedic else ""}
      {horas_yr_sel}
      base.ultimo_acceso
    FROM base
    LEFT JOIN dim_partners dp ON dp.partner = base.partner
    {"LEFT JOIN cert ON cert.partner = base.partner" if has_cert  else ""}
    {"LEFT JOIN ded  ON ded.partner  = base.partner" if has_dedic else ""}
    {"LEFT JOIN ins  ON ins.partner  = base.partner" if has_inscr else ""}
    ORDER BY {order} DESC NULLS LAST, total_altas DESC
    """
    tables.append(("resumen_partner", "r_resumen_partner", sql_resumen))

    # ── r_evolucion_mensual ────────────────────────────────────────────────────
    if has_inscr:
        tables.append(("evolucion_mensual", "r_evolucion_mensual", """
        WITH altas AS (
          SELECT partner, strftime(fecha_alta, '%Y-%m') AS mes, count(*) AS altas
          FROM f_usuarios GROUP BY 1, 2
        ),
        inscritos AS (
          SELECT partner, mes_inscripcion AS mes, count(DISTINCT userid) AS inscritos
          FROM f_inscripciones GROUP BY 1, 2
        ),
        certificados AS (
          SELECT partner, strftime(fecha_nota, '%Y-%m') AS mes,
                 count(DISTINCT CASE WHEN aprobado THEN userid END) AS certificados
          FROM f_certificaciones GROUP BY 1, 2
        ),
        horas AS (
          SELECT partner, mes, SUM(horas) AS horas, count(DISTINCT userid) AS usuarios_activos
          FROM f_dedicacion GROUP BY 1, 2
        )
        SELECT
          COALESCE(a.partner, i.partner, c.partner, h.partner) AS partner,
          COALESCE(a.mes,     i.mes,     c.mes,     h.mes)     AS mes,
          a.altas, i.inscritos, c.certificados, h.horas, h.usuarios_activos
        FROM altas a
        FULL OUTER JOIN inscritos    i USING (partner, mes)
        FULL OUTER JOIN certificados c USING (partner, mes)
        FULL OUTER JOIN horas        h USING (partner, mes)
        ORDER BY partner, mes
        """))

    # ── r_partner_categoria ────────────────────────────────────────────────────
    if has_cert:
        tables.append(("partner_categoria", "r_partner_categoria", """
        SELECT
          fu.partner, dc.categoria,
          count(DISTINCT fc.userid)                                AS alumnos,
          count(DISTINCT CASE WHEN fc.aprobado THEN fc.userid END) AS aprobados
        FROM f_certificaciones fc
        JOIN dim_cursos dc ON dc.course_id = fc.course_id
        JOIN f_usuarios fu ON fu.userid    = fc.userid
        GROUP BY fu.partner, dc.categoria
        ORDER BY fu.partner, aprobados DESC
        """))

    # ── r_partner_version ──────────────────────────────────────────────────────
    if has_cert:
        tables.append(("partner_version", "r_partner_version", """
        SELECT
          fu.partner,
          dc.version,
          dc.categoria,
          dc.course_name,
          count(DISTINCT fc.userid)                                AS alumnos,
          count(DISTINCT CASE WHEN fc.aprobado THEN fc.userid END) AS aprobados
        FROM f_certificaciones fc
        JOIN dim_cursos dc ON dc.course_id = fc.course_id
        JOIN f_usuarios fu ON fu.userid    = fc.userid
        WHERE dc.version IS NOT NULL
        GROUP BY fu.partner, dc.version, dc.categoria, dc.course_name
        ORDER BY fu.partner, dc.version, dc.categoria, dc.course_name
        """))

    # ── r_detalle_certificados ─────────────────────────────────────────────────
    if has_cert:
        tables.append(("detalle_certificados", "r_detalle_certificados", """
        SELECT
          u.userid, u.username, u.nombre_completo, u.email, u.partner,
          dc.course_name, dc.categoria, dc.version, dc.idioma,
          fc.finalgrade, fc.aprobado, fc.fecha_nota
        FROM f_certificaciones fc
        JOIN f_usuarios u  ON u.userid    = fc.userid
        JOIN dim_cursos dc ON dc.course_id = fc.course_id
        WHERE fc.aprobado = TRUE
        ORDER BY fc.fecha_nota DESC
        """))

    # ── r_alertas ──────────────────────────────────────────────────────────────
    tables.append(("alertas", "r_alertas", """
    SELECT
      partner,
      MAX(ultimo_acceso)::DATE AS ultimo_acceso,
      datediff('day', MAX(ultimo_acceso)::DATE, CURRENT_DATE) AS dias_sin_actividad
    FROM f_usuarios
    WHERE ultimo_acceso IS NOT NULL
    GROUP BY partner
    HAVING MAX(ultimo_acceso) < CURRENT_DATE - INTERVAL '30 days'
    ORDER BY dias_sin_actividad DESC
    """))

    return tables


# ── Excel ─────────────────────────────────────────────────────────────────────

HEADER_FILL  = PatternFill("solid", fgColor="1F4E79")
HEADER_FONT  = Font(bold=True, color="FFFFFF", size=10)
ALT_FILL     = PatternFill("solid", fgColor="EBF3FB")
NORMAL_FONT  = Font(size=10)


def _strip_tz(val):
    """Excel no admite datetimes con timezone — los convierte a naive."""
    if hasattr(val, "tzinfo") and val.tzinfo is not None:
        return val.replace(tzinfo=None)
    return val


def _write_sheet(ws, rows: list[tuple], columns: list[str]) -> None:
    ws.append(columns)
    for cell in ws[1]:
        cell.font  = HEADER_FONT
        cell.fill  = HEADER_FILL
        cell.alignment = Alignment(horizontal="center")

    for i, row in enumerate(rows, start=2):
        ws.append([_strip_tz(v) for v in row])
        if i % 2 == 0:
            for cell in ws[i]:
                cell.fill = ALT_FILL
                cell.font = NORMAL_FONT

    for col_idx, _ in enumerate(columns, start=1):
        col_letter = get_column_letter(col_idx)
        max_len = max(
            (len(str(ws.cell(row=r, column=col_idx).value or "")) for r in range(1, ws.max_row + 1)),
            default=8,
        )
        ws.column_dimensions[col_letter].width = min(max_len + 2, 40)


def export_excel(con: duckdb.DuckDBPyConnection,
                 semantic_tables: set[str],
                 output_path: Path) -> list[str]:
    wb = openpyxl.Workbook()
    wb.remove(wb.active)   # eliminar hoja vacía por defecto
    generated = []

    for sheet_name, table_name, sql in reporting_queries(semantic_tables, con):
        try:
            con.execute(f"CREATE OR REPLACE TABLE {table_name} AS {sql}")
            rel = con.execute(f"SELECT * FROM {table_name}")
            columns = [desc[0] for desc in rel.description]
            rows    = rel.fetchall()
            ws = wb.create_sheet(title=sheet_name[:31])
            _write_sheet(ws, rows, columns)
            print(f"  {OK}  {sheet_name}: {len(rows):,} filas")
            generated.append(sheet_name)
        except Exception as e:
            print(f"  {WARN}  {sheet_name}: {e}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(output_path)
    return generated


def print_kpis(con: duckdb.DuckDBPyConnection) -> None:
    def q(sql):
        try:
            return con.execute(sql).fetchone()[0]
        except Exception:
            return "—"

    print(f"\n  {SEP}")
    print("  KPIs resumen\n")
    print(f"  {'Partners:':<32} {q('SELECT count(DISTINCT partner) FROM f_usuarios')}")
    print(f"  {'Usuarios totales:':<32} {q('SELECT count(*) FROM f_usuarios')}")
    print(f"  {'Usuarios activos:':<32} {q('SELECT count(*) FROM f_usuarios WHERE activo')}")
    print(f"  {'Cohortes:':<32} {q('SELECT count(*) FROM dim_cohortes')}")
    print(f"  {'Cursos (total):':<32} {q('SELECT count(*) FROM dim_cursos')}")
    print(f"  {'Cursos certificación:':<32} {q('SELECT count(*) FROM dim_cursos WHERE es_certificacion')}")
    print(f"  {'Inscripciones (cohort):':<32} {q('SELECT count(*) FROM f_inscripciones')}")
    print(f"  {'Notas finales curso:':<32} {q('SELECT count(*) FROM f_certificaciones')}")
    print(f"  {'  Aprobadas (>=70):':<32} {q('SELECT count(*) FROM f_certificaciones WHERE aprobado')}")
    print(f"  {'Sesiones asistencia:':<32} {q('SELECT count(*) FROM raw_attendance_sessions')}")
    print(f"  {'Horas totales:':<32} {q('SELECT ROUND(SUM(horas), 0) FROM f_dedicacion')}")
    print()


def apply_partner_filter(con: duckdb.DuckDBPyConnection, partner: str) -> None:
    """Reemplaza las tablas semánticas por vistas filtradas a un único partner."""
    filterable = {
        "f_usuarios":        "partner",
        "f_inscripciones":   "partner",
        "f_certificaciones": "partner",
        "f_actividad":       "partner",
        "f_dedicacion":      "partner",
    }
    for table, col in filterable.items():
        try:
            con.execute(
                f"CREATE OR REPLACE VIEW {table} AS "
                f"SELECT * FROM {table}_all WHERE {col} = '{partner}'"
            )
        except Exception:
            pass


def main():
    parser = argparse.ArgumentParser(description="Validación local semántica + reporting (Excel)")
    parser.add_argument("--workdir", help="Directorio con los Parquet (por defecto: último snapshot)")
    parser.add_argument("--output", help="Ruta del Excel de salida (por defecto: informe_formacion[_partner].xlsx)")
    parser.add_argument("--partner", help="Filtrar informe a un único partner (ej: pichincha)")
    args = parser.parse_args()

    workdir = Path(args.workdir) if args.workdir else latest_workdir()
    if not workdir or not workdir.exists():
        print(f"{FAIL} No se encontró workdir. Ejecuta primero:")
        print("       python3 -m src.agent.main --skip-upload")
        sys.exit(1)

    partner = args.partner.lower() if args.partner else None
    default_output = (
        f"/tmp/reports_local/informe_{partner}.xlsx" if partner
        else "/tmp/reports_local/informe_formacion.xlsx"
    )
    output_path = Path(args.output) if args.output else Path(default_output)

    print(f"\n{'═' * 60}")
    print(f"  Validación local — {workdir.name}")
    print(f"  Fuente:  {workdir}")
    if partner:
        print(f"  Filtro:  partner = '{partner}'")
    print(f"  Salida:  {output_path}")
    print(f"{'═' * 60}\n")

    con = duckdb.connect()

    print(f"  {INFO}  Construyendo capa semántica...")
    semantic_tables = build_semantic(con, workdir)

    if partner:
        # Renombrar tablas originales y crear vistas filtradas
        for t in ["f_usuarios", "f_inscripciones", "f_certificaciones", "f_actividad", "f_dedicacion"]:
            if t in semantic_tables:
                con.execute(f"ALTER TABLE {t} RENAME TO {t}_all")
                con.execute(f"CREATE VIEW {t} AS SELECT * FROM {t}_all WHERE partner = '{partner}'")

    print(f"  {OK}  {len(semantic_tables)} tablas semánticas listas\n")

    print(f"  {INFO}  Generando hojas Excel...")
    sheets = export_excel(con, semantic_tables, output_path)

    print_kpis(con)
    con.close()

    print(f"  {OK}  Excel generado: {output_path}")
    print(f"       {len(sheets)} hojas: {', '.join(sheets)}\n")


if __name__ == "__main__":
    main()
