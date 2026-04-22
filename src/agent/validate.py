"""
agent/validate.py — Validación técnica de los ficheros Parquet locales.

Comprueba que lo serializado coincide con lo extraído antes de subir a HDFS.
No hace comprobaciones de negocio (eso es sanity.py).
"""

import hashlib
import pyarrow.parquet as pq

from shared.utils import log


def checksum(path: str) -> str:
    """SHA-256 del fichero Parquet."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def assert_row_count(expected: int, path: str, dataset: str) -> None:
    """
    Verifica que el Parquet escrito tiene exactamente las mismas filas
    que la lista extraída de Moodle. Tolerancia: cero.
    """
    actual = pq.read_metadata(path).num_rows
    if actual != expected:
        raise ValueError(
            f"[{dataset}] Row count mismatch: extraídas={expected}, "
            f"en Parquet={actual}"
        )
    log(f"{dataset}: {actual} filas  checksum OK", "✓")


def validate_dataset(rows: list[dict], path: str, dataset: str) -> str:
    """
    Valida un dataset completo: row count + checksum.
    Devuelve el checksum SHA-256 para adjuntarlo al resumen de ejecución.
    """
    assert_row_count(len(rows), path, dataset)
    cs = checksum(path)
    return cs


def assert_hdfs_present(items: list[dict], filename: str, dataset: str) -> None:
    """
    Tras subir a HDFS, verifica que el fichero aparece en el listado
    de Rocket (findByPath) con size > 0.
    """
    matches = [
        item for item in items
        if item.get("name", "").endswith(filename)
        and item.get("type") == "file"
        and item.get("size", 0) > 0
    ]
    if not matches:
        raise ValueError(
            f"[{dataset}] Fichero '{filename}' no encontrado en HDFS "
            f"tras la subida, o size=0"
        )
    log(f"{dataset}: presente en HDFS, size={matches[0]['size']} bytes", "✓")
