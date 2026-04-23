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
