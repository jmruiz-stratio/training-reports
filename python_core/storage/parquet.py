import os
import pyarrow as pa
import pyarrow.parquet as pq


def write(rows: list[dict], dataset: str, workdir: str) -> str:
    os.makedirs(workdir, exist_ok=True)
    path = os.path.join(workdir, f"{dataset}.parquet")
    table = pa.Table.from_pylist(rows) if rows else pa.table({})
    pq.write_table(table, path, compression="snappy")
    return path


def row_count(path: str) -> int:
    return pq.read_metadata(path).num_rows
