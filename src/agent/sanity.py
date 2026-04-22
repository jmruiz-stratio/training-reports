"""
agent/sanity.py — Validación de negocio pre-subida mediante DuckDB.

Lee los ficheros Parquet locales (todavía no subidos a HDFS) y ejecuta
consultas SQL que adelantan los KPIs del dashboard, permitiendo detectar
anomalías antes de comprometer los datos en producción.

Las consultas usan la misma lógica que las vistas semánticas (§8.2):
  - Derivación de partner (CLAUDE.md §6.2 f_usuarios)
  - Clasificación de cohortes en categorías y versiones
  - Identificación de cursos certificación
  - Conteo de aprobados (graderaw >= 70)

Dependencia: duckdb (ver pyproject.toml)
"""

import os
import duckdb

OK   = "\033[92m✓\033[0m"
WARN = "\033[93m⚠\033[0m"
INFO = "\033[94m·\033[0m"
SEP  = "─" * 56


def _tbl(con, dataset: str, workdir: str) -> bool:
    """Registra el Parquet como vista en DuckDB. Devuelve False si no existe."""
    path = os.path.join(workdir, f"{dataset}.parquet")
    if not os.path.exists(path):
        return False
    con.execute(f"CREATE OR REPLACE VIEW {dataset} AS SELECT * FROM read_parquet('{path}')")
    return True


def _print_table(rows, headers: list[str]) -> None:
    """Imprime una tabla ASCII simple."""
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(str(cell)))
    fmt = "    " + "  ".join(f"{{:<{w}}}" for w in widths)
    print(fmt.format(*headers))
    print("    " + "  ".join("─" * w for w in widths))
    for row in rows:
        print(fmt.format(*[str(c) for c in row]))


def run(workdir: str) -> dict:
    """
    Ejecuta todas las comprobaciones de negocio y devuelve un dict con
    los KPIs clave para incluir en el resumen de ejecución.

    Devuelve {} si no hay ficheros Parquet disponibles.
    """
    con = duckdb.connect()
    disponibles = {
        ds: _tbl(con, ds, workdir)
        for ds in ["users", "courses", "cohorts", "cohort_members",
                   "user_courses", "user_grades", "cohort_members_ext"]
    }

    kpis = {}

    print(f"\n  {INFO}  Validación de negocio (pre-subida)")
    print(f"  {SEP}")

    # ── USUARIOS ──────────────────────────────────────────────────────────────
    if disponibles["users"]:
        total = con.execute("SELECT count(*) FROM users").fetchone()[0]
        kpis["total_users"] = total
        print(f"\n  USUARIOS  ({total} filas)")

        # Partners derivados — lógica canónica de f_usuarios
        partner_sql = """
            SELECT
              CASE
                WHEN lower(email) LIKE '%stratio%'
                  OR lower(username) LIKE '%stratio%' THEN 'stratio'
                ELSE list_last(string_split(username, '-'))
              END AS partner,
              count(*) AS n_usuarios
            FROM users
            GROUP BY 1
            ORDER BY 2 DESC
            LIMIT 15
        """
        rows = con.execute(partner_sql).fetchall()
        n_partners = con.execute("""
            SELECT count(DISTINCT
              CASE WHEN lower(email) LIKE '%stratio%'
                     OR lower(username) LIKE '%stratio%' THEN 'stratio'
                   ELSE list_last(string_split(username, '-')) END)
            FROM users
        """).fetchone()[0]
        kpis["n_partners"] = n_partners
        print(f"    Partners distintos: {n_partners}")
        _print_table(rows, ["partner", "usuarios"])

        activos = con.execute(
            "SELECT count(*) FROM users WHERE suspended = 0 OR suspended IS NULL"
        ).fetchone()[0]
        kpis["usuarios_activos"] = activos
        print(f"\n    Activos (no suspendidos): {activos} / {total}")

    # ── COHORTES ──────────────────────────────────────────────────────────────
    if disponibles["cohorts"]:
        total = con.execute("SELECT count(*) FROM cohorts").fetchone()[0]
        kpis["total_cohorts"] = total
        print(f"\n  COHORTES  ({total} filas)")

        cat_rows = con.execute("""
            SELECT
              CASE
                WHEN lower(name) LIKE '%governance%'      THEN 'Governance'
                WHEN lower(name) LIKE '%data processing%' THEN 'Data Processing'
                WHEN lower(name) LIKE '%intelligence%'    THEN 'Intelligence'
                WHEN lower(name) LIKE '%operaciones%'     THEN 'Operaciones'
                ELSE 'Otros'
              END AS categoria,
              count(*) AS n
            FROM cohorts
            GROUP BY 1 ORDER BY 2 DESC
        """).fetchall()
        print("    Por categoría:")
        _print_table(cat_rows, ["categoria", "n"])

        ver_rows = con.execute("""
            SELECT
              COALESCE(NULLIF(regexp_extract(name,'(1[34]\\.[0-9])',1),''), '(sin versión)') AS version,
              count(*) AS n
            FROM cohorts
            GROUP BY 1 ORDER BY 1
        """).fetchall()
        print("    Por versión:")
        _print_table(ver_rows, ["version", "n"])

    # ── CURSOS ────────────────────────────────────────────────────────────────
    if disponibles["courses"]:
        total = con.execute("SELECT count(*) FROM courses").fetchone()[0]
        kpis["total_courses"] = total
        print(f"\n  CURSOS  ({total} filas)")

        n_cert = con.execute("""
            SELECT count(*) FROM courses
            WHERE lower(fullname) LIKE '%certificaci%'
               OR lower(fullname) LIKE '%certification%'
        """).fetchone()[0]
        kpis["cursos_certificacion"] = n_cert
        print(f"    Certificación: {n_cert}  |  Otros: {total - n_cert}")

        cat_rows = con.execute("""
            SELECT
              CASE
                WHEN lower(fullname) LIKE '%governance%'      THEN 'Governance'
                WHEN lower(fullname) LIKE '%data processing%' THEN 'Data Processing'
                WHEN lower(fullname) LIKE '%intelligence%'    THEN 'Intelligence'
                WHEN lower(fullname) LIKE '%operaciones%'     THEN 'Operaciones'
                ELSE 'Otros'
              END AS categoria,
              count(*) AS n
            FROM courses
            GROUP BY 1 ORDER BY 2 DESC
        """).fetchall()
        print("    Por categoría:")
        _print_table(cat_rows, ["categoria", "n"])

    # ── INSCRIPCIONES (cohort_members / cohort_members_ext) ───────────────────
    src = "cohort_members_ext" if disponibles["cohort_members_ext"] else \
          "cohort_members"     if disponibles["cohort_members"]     else None
    if src:
        total = con.execute(f"SELECT count(*) FROM {src}").fetchone()[0]
        n_users  = con.execute(f"SELECT count(DISTINCT userid)  FROM {src}").fetchone()[0]
        n_cohort = con.execute(f"SELECT count(DISTINCT cohortid) FROM {src}").fetchone()[0]
        kpis["total_inscripciones"] = total
        print(f"\n  INSCRIPCIONES  ({src}, {total} filas)")
        print(f"    Usuarios únicos: {n_users}  |  Cohortes únicas: {n_cohort}")

        if src == "cohort_members_ext":
            meses = con.execute("""
                SELECT strftime(to_timestamp(timeadded), '%Y-%m') AS mes,
                       count(*) AS altas
                FROM cohort_members_ext
                WHERE timeadded IS NOT NULL
                GROUP BY 1 ORDER BY 1 DESC LIMIT 6
            """).fetchall()
            if meses:
                print("    Últimas altas por mes:")
                _print_table(meses, ["mes", "altas"])

    # ── NOTAS / CERTIFICACIONES ───────────────────────────────────────────────
    if disponibles["user_grades"]:
        total = con.execute("SELECT count(*) FROM user_grades").fetchone()[0]
        kpis["total_grades"] = total
        print(f"\n  NOTAS  ({total} filas)")

        # La función custom devuelve solo notas de curso (itemtype='course' filtrado en PHP)
        aprobados_rows = con.execute("""
            SELECT
              graderaw >= 70  AS aprobado,
              count(*)        AS n
            FROM user_grades
            WHERE graderaw IS NOT NULL
            GROUP BY 1 ORDER BY 1 DESC
        """).fetchall()
        _print_table(aprobados_rows, ["aprobado", "n"])

        aprobados = con.execute("""
            SELECT count(*) FROM user_grades WHERE graderaw >= 70
        """).fetchone()[0]
        kpis["certificaciones_aprobadas"] = aprobados
        print(f"    Certificaciones aprobadas (graderaw>=70): {aprobados}")

    # ── ALERTAS ───────────────────────────────────────────────────────────────
    print(f"\n  {SEP}")
    alertas = _check_alertas(con, disponibles, kpis)
    if alertas:
        for a in alertas:
            print(f"  {WARN}  {a}")
    else:
        print(f"  {OK}  Sin alertas de negocio detectadas")

    print()
    con.close()
    return kpis


def _check_alertas(con, disponibles: dict, kpis: dict) -> list[str]:
    alertas = []

    if kpis.get("total_users", 0) == 0:
        alertas.append("Sin usuarios: algo falló en la extracción")

    if kpis.get("n_partners", 0) == 0:
        alertas.append("No se derivó ningún partner de los usernames")

    if kpis.get("total_courses", 0) == 0:
        alertas.append("Sin cursos extraídos")

    if kpis.get("cursos_certificacion", 0) == 0 and kpis.get("total_courses", 0) > 0:
        alertas.append("Ningún curso identificado como certificación "
                       "(revisar nombres de cursos)")

    if kpis.get("total_cohorts", 0) == 0:
        alertas.append("Sin cohortes extraídas")

    # Usuarios sin partner derivable (username sin '-')
    if disponibles["users"]:
        sin_guion = con.execute("""
            SELECT count(*) FROM users
            WHERE lower(email) NOT LIKE '%stratio%'
              AND lower(username) NOT LIKE '%stratio%'
              AND username NOT LIKE '%-%'
        """).fetchone()[0]
        if sin_guion > 0:
            alertas.append(
                f"{sin_guion} usuario(s) sin '-' en username: "
                f"partner no derivable (revisar regla)"
            )

    return alertas
