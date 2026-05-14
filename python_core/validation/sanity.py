"""Business validation and snapshot comparison helpers."""

import os
import duckdb


def run(workdir: str) -> dict:
    con = duckdb.connect()
    for ds in ["users", "courses", "cohorts", "cohort_members", "user_grades", "cohort_members_ext"]:
        p = os.path.join(workdir, f"{ds}.parquet")
        if os.path.exists(p):
            con.execute(f"CREATE OR REPLACE VIEW {ds} AS SELECT * FROM read_parquet('{p}')")
    kpis = {}
    for ds in ["users", "courses", "cohorts", "user_grades"]:
        try:
            kpis[f"total_{ds}"] = con.execute(f"SELECT count(*) FROM {ds}").fetchone()[0]
        except Exception:
            kpis[f"total_{ds}"] = 0
    if kpis.get("total_users", 0):
        kpis["n_partners"] = con.execute("""
            SELECT count(DISTINCT CASE WHEN lower(email) LIKE '%stratio%' OR lower(username) LIKE '%stratio%'
            THEN 'stratio' ELSE list_last(string_split(username, '-')) END) FROM users
        """).fetchone()[0]
    con.close()
    return kpis


def compare_snapshot_counts(base_dir: str, target_dir: str, datasets: list[str]) -> list[dict]:
    out = []
    for ds in datasets:
        b = os.path.join(base_dir, f"{ds}.parquet")
        t = os.path.join(target_dir, f"{ds}.parquet")
        b_count = duckdb.sql(f"SELECT count(*) FROM read_parquet('{b}')").fetchone()[0] if os.path.exists(b) else None
        t_count = duckdb.sql(f"SELECT count(*) FROM read_parquet('{t}')").fetchone()[0] if os.path.exists(t) else None
        out.append({"dataset": ds, "base": b_count, "target": t_count, "delta": None if None in (b_count, t_count) else t_count - b_count})
    return out
