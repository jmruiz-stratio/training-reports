import hashlib
import pyarrow.parquet as pq


def checksum(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def assert_row_count(expected: int, path: str, dataset: str) -> None:
    actual = pq.read_metadata(path).num_rows
    if actual != expected:
        raise ValueError(f"[{dataset}] Row count mismatch: {expected} != {actual}")


def validate_dataset(rows: list[dict], path: str, dataset: str) -> str:
    assert_row_count(len(rows), path, dataset)
    return checksum(path)
