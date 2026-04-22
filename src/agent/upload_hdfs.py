"""
Subida de ficheros a HDFS mediante la API de Rocket (Stratio).

Flujo de subida en 2 pasos:
  1. POST   /uploadLocalFile   — sube el binario al tmp del servidor Rocket
                                 y devuelve el dockerPath (ruta temporal en el contenedor)
  2. POST   /putLocalFileToHdfs — mueve el fichero del tmp de Rocket al path HDFS destino

Otros endpoints:
  POST   /findByPath — lista un directorio HDFS; respuesta: array JSON directo
  DELETE /delete     — borra uno o varios paths HDFS; respuesta: "OK" (text/plain)
  GET    /getFilesystems — lista filesystems disponibles

Autenticación: cookies stratio-cookie + JSESSIONID (obtenidas con
get_practices_cookies.py del proyecto training-agents).
"""

import json
import os
import uuid as _uuid
import urllib.request
import urllib.error
from datetime import date

# Filesystem ID del tenant formacion — obtenido de GET /getFilesystems
FILESYSTEM = {"id": "hdfs.formacion-datastores", "type": "HDFS"}

_API_PATH = "/rocketf/fileBrowser"


def _base(rocket_url: str) -> str:
    return rocket_url.rstrip("/") + _API_PATH


def _cookies_header(cookies: dict) -> str:
    return "; ".join(f"{k}={v}" for k, v in cookies.items())


def _json_request(url: str, payload: dict, cookies: dict, method: str = "POST") -> object:
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        url,
        data=body,
        method=method,
        headers={
            "Content-Type": "application/json",
            "Cookie": _cookies_header(cookies),
        },
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        raw = r.read()
        if not raw.strip():
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return raw.decode()


def _build_multipart(filename: str, file_bytes: bytes) -> tuple[bytes, str]:
    boundary = _uuid.uuid4().hex
    body = b"".join([
        f"--{boundary}\r\n".encode(),
        f'Content-Disposition: form-data; name="binary"; filename="{filename}"\r\n'.encode(),
        b"Content-Type: application/octet-stream\r\n\r\n",
        file_bytes,
        f"\r\n--{boundary}--\r\n".encode(),
    ])
    return body, f"multipart/form-data; boundary={boundary}"


def _upload_local_file(local_path: str, rocket_url: str, cookies: dict) -> str:
    """
    Paso 1: sube el fichero al tmp de Rocket.
    Devuelve el dockerPath (ej: /tmp/uploads/{uuid}/filename).
    """
    filename = os.path.basename(local_path)
    with open(local_path, "rb") as f:
        file_bytes = f.read()

    body, content_type = _build_multipart(filename, file_bytes)
    req = urllib.request.Request(
        f"{_base(rocket_url)}/uploadLocalFile",
        data=body,
        method="POST",
        headers={
            "Content-Type": content_type,
            "Cookie": _cookies_header(cookies),
        },
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        raw = r.read()

    # La respuesta puede ser el dockerPath como string plano o como campo de un dict
    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        return raw.decode().strip()

    if isinstance(result, str):
        return result
    if isinstance(result, dict):
        for key in ("dockerPath", "path", "filePath", "tmpPath"):
            if key in result:
                return result[key]
    raise RuntimeError(f"uploadLocalFile: respuesta inesperada: {result!r}")


def _put_to_hdfs(docker_path: str, hdfs_dir: str, rocket_url: str, cookies: dict) -> None:
    """
    Paso 2: mueve el fichero del tmp de Rocket al directorio HDFS destino.
    Si el directorio no existe en HDFS, Rocket lo crea.
    """
    payload = {
        "pathHdfs": hdfs_dir,
        "dockerPath": docker_path,
        "targetFilesystem": FILESYSTEM,
    }
    _json_request(f"{_base(rocket_url)}/putLocalFileToHdfs", payload, cookies)


def put(local_path: str, hdfs_dir: str, rocket_url: str, cookies: dict) -> str:
    """
    Sube local_path al directorio hdfs_dir en HDFS.
    Devuelve la ruta HDFS completa del fichero subido.
    """
    docker_path = _upload_local_file(local_path, rocket_url, cookies)
    _put_to_hdfs(docker_path, hdfs_dir, rocket_url, cookies)
    return f"{hdfs_dir}/{os.path.basename(local_path)}"


def list_path(hdfs_path: str, rocket_url: str, cookies: dict) -> list[dict]:
    """
    Lista ficheros y directorios en hdfs_path.
    Devuelve lista de dicts con campos: name, type, size, owner, group, permissions, lastUpdated.
    lastUpdated es unix timestamp en milisegundos.
    """
    payload = {"pathHdfs": hdfs_path, "targetFilesystem": FILESYSTEM}
    result = _json_request(f"{_base(rocket_url)}/findByPath", payload, cookies)
    if isinstance(result, list):
        return result
    return []


def partition_path(dataset: str, ingest_date: date, hdfs_base: str) -> str:
    """Construye la ruta de partición HDFS: {hdfs_base}/{dataset}/ingest_date=YYYY-MM-DD."""
    return f"{hdfs_base}/{dataset}/ingest_date={ingest_date.isoformat()}"


def delete_partition(hdfs_path: str, rocket_url: str, cookies: dict) -> None:
    """
    Borra un directorio (o fichero) en HDFS.
    Acepta rutas individuales; para borrar una partición entera pasa la ruta del directorio.
    """
    payload = {
        "files": [{"path": hdfs_path}],
        "targetFilesystem": FILESYSTEM,
    }
    _json_request(f"{_base(rocket_url)}/delete", payload, cookies, method="DELETE")


def delete_paths(hdfs_paths: list[str], rocket_url: str, cookies: dict) -> None:
    """Borra múltiples paths HDFS en una sola llamada."""
    payload = {
        "files": [{"path": p} for p in hdfs_paths],
        "targetFilesystem": FILESYSTEM,
    }
    _json_request(f"{_base(rocket_url)}/delete", payload, cookies, method="DELETE")


def get_filesystems(rocket_url: str, cookies: dict) -> list[dict]:
    """
    Devuelve los filesystems disponibles.
    Útil para diagnóstico y para confirmar el ID del filesystem.
    """
    req = urllib.request.Request(
        f"{_base(rocket_url)}/getFilesystems",
        method="GET",
        headers={"Cookie": _cookies_header(cookies)},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())
