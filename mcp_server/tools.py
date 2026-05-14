from skill.analytics import partner_kpis
from python_core.validation.sanity import run as validate_snapshot, compare_snapshot_counts


def list_training_partners(workdir: str) -> list[str]:
    return [r["partner"] for r in partner_kpis(workdir)]


def get_partner_kpis(workdir: str, partner: str) -> dict:
    for row in partner_kpis(workdir):
        if row["partner"] == partner:
            return row
    return {"partner": partner, "users": 0}


def validate_latest_snapshot(workdir: str) -> dict:
    return validate_snapshot(workdir)


def compare_snapshots(base_dir: str, target_dir: str) -> list[dict]:
    datasets = ["users", "courses", "cohorts", "user_grades"]
    return compare_snapshot_counts(base_dir, target_dir, datasets)
