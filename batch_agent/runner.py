import os
from datetime import date

from python_core.auth import get_rocket_cookies
from python_core.config import load_settings, DATASETS_ALL
from python_core.extraction import run_all
from python_core.storage import hdfs
from python_core.storage.parquet import write
from python_core.validation.technical import validate_dataset
from python_core.validation.sanity import run as run_sanity
from python_core.utils import log


def _upload_parquets(
    parquet_paths: dict[str, str],
    ingest_date: date,
    hdfs_base_path: str,
    stratio_url: str,
    cookies: dict[str, str],
) -> list[str]:
    uploaded: list[str] = []
    for dataset, local_path in parquet_paths.items():
        hdfs_dir = hdfs.partition_path(dataset, ingest_date, hdfs_base_path)
        log(f"Subiendo {dataset} -> {hdfs_dir}")
        hdfs.put(local_path, hdfs_dir, stratio_url, cookies)
        uploaded.append(dataset)
    return uploaded


def ingest_daily(ingest_date: date, skip_upload: bool = False) -> dict:
    settings = load_settings()
    if not settings.moodle_url or not settings.moodle_token:
        raise RuntimeError("MOODLE_URL/MOODLE_TOKEN no definidos")

    workdir = os.path.join(settings.workdir, ingest_date.isoformat())
    os.makedirs(workdir, exist_ok=True)

    datasets = run_all(settings.moodle_url, settings.moodle_token, DATASETS_ALL)
    checksums: dict[str, str] = {}
    parquet_paths: dict[str, str] = {}

    for dataset, rows in datasets.items():
        if not rows:
            continue
        parquet_path = write(rows, dataset, workdir)
        checksums[dataset] = validate_dataset(rows, parquet_path, dataset)
        parquet_paths[dataset] = parquet_path

    kpis = run_sanity(workdir)

    uploaded: list[str] = []
    if not skip_upload and parquet_paths:
        if not settings.stratio_url:
            raise RuntimeError("STRATIO_URL no definido para subida a HDFS")
        cookies = get_rocket_cookies(settings)
        uploaded = _upload_parquets(
            parquet_paths, ingest_date, settings.hdfs_base_path, settings.stratio_url, cookies
        )

    return {
        "workdir": workdir,
        "checksums": checksums,
        "kpis": kpis,
        "upload_skipped": skip_upload,
        "datasets_uploaded": uploaded,
    }
