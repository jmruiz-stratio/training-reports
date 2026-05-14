import argparse
import json
from datetime import date

from python_core.config import DATASETS_ALL
from python_core.validation.sanity import run as validate_snapshot, compare_snapshot_counts
from .runner import ingest_daily


def main() -> int:
    parser = argparse.ArgumentParser(description="Batch agent CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    ingest = sub.add_parser("ingest", help="Ingest operations")
    ingest_sub = ingest.add_subparsers(dest="scope", required=True)
    ingest_daily_cmd = ingest_sub.add_parser("daily", help="Run daily ingestion")
    ingest_daily_cmd.add_argument("--date", default=date.today().isoformat())
    ingest_daily_cmd.add_argument("--skip-upload", action="store_true", help="Do not upload to HDFS")
    ingest_daily_cmd.add_argument("--dry-run", action="store_true", help="Alias for --skip-upload")

    validate = sub.add_parser("validate", help="Validate snapshot")
    validate_sub = validate.add_subparsers(dest="scope", required=True)
    validate_snapshot_cmd = validate_sub.add_parser("snapshot")
    validate_snapshot_cmd.add_argument("workdir")

    compare = sub.add_parser("compare", help="Compare snapshots")
    compare_sub = compare.add_subparsers(dest="scope", required=True)
    compare_snapshots_cmd = compare_sub.add_parser("snapshots")
    compare_snapshots_cmd.add_argument("base_dir")
    compare_snapshots_cmd.add_argument("target_dir")

    args = parser.parse_args()

    if args.cmd == "ingest" and args.scope == "daily":
        result = ingest_daily(
            date.fromisoformat(args.date),
            skip_upload=(args.skip_upload or args.dry_run),
        )
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    if args.cmd == "validate" and args.scope == "snapshot":
        print(json.dumps(validate_snapshot(args.workdir), indent=2, ensure_ascii=False))
        return 0

    if args.cmd == "compare" and args.scope == "snapshots":
        print(json.dumps(compare_snapshot_counts(args.base_dir, args.target_dir, DATASETS_ALL), indent=2, ensure_ascii=False))
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
