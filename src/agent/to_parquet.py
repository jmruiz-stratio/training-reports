"""
agent/to_parquet.py — Serialización de listas de dicts a Parquet con pyarrow.
"""

import os
import pyarrow as pa
import pyarrow.parquet as pq


def write(rows: list[dict], dataset: str, workdir: str) -> str:
    """
    Convierte rows a Parquet y lo guarda en workdir/{dataset}.parquet.
    Devuelve la ruta del fichero escrito.
    Si rows está vacío escribe un Parquet vacío (schema inferido como 0 columnas).
    """
    os.makedirs(workdir, exist_ok=True)
    path = os.path.join(workdir, f"{dataset}.parquet")

    if rows:
        table = pa.Table.from_pylist(rows)
    else:
        table = pa.table({})

    pq.write_table(table, path, compression="snappy")
    return path


def row_count_local(path: str) -> int:
    """Número de filas del Parquet sin cargarlo entero en memoria."""
    return pq.read_metadata(path).num_rows
