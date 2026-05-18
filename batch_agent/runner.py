import os
from datetime import date

from python_core.config import load_settings, DATASETS_ALL
from python_core.extraction import run_all
from python_core.storage.parquet import write
from python_core.validation.technical import validate_dataset
from python_core.validation.sanity import run as run_sanity


def ingest_daily(ingest_date: date) -> dict:
    settings = load_settings()
    if not settings.moodle_url or not settings.moodle_token:
        raise RuntimeError("MOODLE_URL/MOODLE_TOKEN no definidos")

    workdir = os.path.join(settings.workdir, ingest_date.isoformat())
    os.makedirs(workdir, exist_ok=True)

    datasets = run_all(settings.moodle_url, settings.moodle_token, DATASETS_ALL)
    checksums: dict[str, str] = {}

    for dataset, rows in datasets.items():
        if not rows:
            continue
        parquet_path = write(rows, dataset, workdir)
        checksums[dataset] = validate_dataset(rows, parquet_path, dataset)

    kpis = run_sanity(workdir)

    return {
        "workdir": workdir,
        "checksums": checksums,
        "kpis": kpis,
    }
