"""Legacy-compatible entrypoint for RAW ingestion.

Supports previous usage:
  python -m src.agent.main --date YYYY-MM-DD [--dry-run|--skip-upload]

And delegates to the new batch architecture for long-term maintenance.
"""

import argparse
from datetime import date

from batch_agent.runner import ingest_daily


def main() -> int:
    parser = argparse.ArgumentParser(description="Legacy RAW ingestion entrypoint")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-upload", action="store_true")
    args = parser.parse_args()

    # Previous behavior treated dry-run as skip upload.
    skip_upload = args.skip_upload or args.dry_run
    result = ingest_daily(date.fromisoformat(args.date), skip_upload=skip_upload)
    print(f"Ingesta completada: {result['workdir']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
