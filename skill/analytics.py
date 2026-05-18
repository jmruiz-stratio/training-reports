from pathlib import Path
import duckdb


def partner_kpis(workdir: str) -> list[dict]:
    users = Path(workdir) / "users.parquet"
    if not users.exists():
        return []
    q = f"""
    SELECT
      CASE WHEN lower(email) LIKE '%stratio%' OR lower(username) LIKE '%stratio%'
           THEN 'stratio' ELSE list_last(string_split(username, '-')) END AS partner,
      count(*) AS users
    FROM read_parquet('{users}')
    GROUP BY 1 ORDER BY 2 DESC
    """
    rows = duckdb.sql(q).fetchall()
    return [{"partner": p, "users": n} for p, n in rows]


def export_partner_kpis_csv(workdir: str, output_csv: str) -> str:
    rows = partner_kpis(workdir)
    import csv
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["partner", "users"])
        w.writeheader()
        w.writerows(rows)
    return output_csv


def _load_reporting_helpers():
    try:
        from src.local_validate import build_semantic, export_excel, reporting_queries
    except SystemExit as e:
        raise RuntimeError("Reporting requiere openpyxl instalado (pip install openpyxl)") from e
    return build_semantic, export_excel, reporting_queries


def export_reporting_package(
    workdir: str,
    output_excel: str,
    output_csv_dir: str,
    partner: str | None = None,
    practices_csv: str | None = None,
) -> dict:
    build_semantic, export_excel, reporting_queries = _load_reporting_helpers()

    base = Path(workdir)
    if not base.exists():
        raise RuntimeError(f"Workdir no encontrado: {workdir}")

    con = duckdb.connect()
    semantic_tables = build_semantic(con, base)

    if partner:
        p = partner.lower()
        for t in ["f_usuarios", "f_inscripciones", "f_certificaciones", "f_actividad", "f_dedicacion"]:
            if t in semantic_tables:
                con.execute(f"ALTER TABLE {t} RENAME TO {t}_all")
                con.execute(f"CREATE VIEW {t} AS SELECT * FROM {t}_all WHERE partner = '{p}'")

    output_excel_path = Path(output_excel)
    pcsv = Path(practices_csv) if practices_csv else Path("reports/sesiones_practicas.csv")
    sheets = export_excel(con, semantic_tables, output_excel_path, pcsv if pcsv.exists() else None)

    csv_dir = Path(output_csv_dir)
    csv_dir.mkdir(parents=True, exist_ok=True)
    exported_csv: list[str] = []

    for sheet_name, table_name, sql in reporting_queries(semantic_tables, con):
        con.execute(f"CREATE OR REPLACE TABLE {table_name} AS {sql}")
        out_csv = csv_dir / f"{sheet_name}.csv"
        con.execute(f"COPY (SELECT * FROM {table_name}) TO '{out_csv}' (HEADER, DELIMITER ',')")
        exported_csv.append(str(out_csv))

    con.close()

    return {
        "excel": str(output_excel_path),
        "sheets": sheets,
        "csv_files": exported_csv,
        "partner_filter": partner,
    }
