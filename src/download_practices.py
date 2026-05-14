#!/usr/bin/env python3
"""
Descarga sesiones de prácticas desde OpenSearch y guarda como CSV.

Uso (con port-forward activo: kubectl port-forward -n formacion-datastores svc/opensearch-coordinator 19200:9200):
  python3 src/download_practices.py

Variables de entorno:
  OS_HOST    host OpenSearch (default: localhost)
  OS_PORT    puerto (default: 19200)
  OS_INDEX   índice (default: practices_sessions)
  TLS_CERT   ruta al certificado cliente (default: secretos/admin/admin.crt)
  TLS_KEY    ruta a la clave privada (default: secretos/admin/admin_private.key)
"""
import argparse
import csv
import json
import os
import ssl
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

OS_HOST   = os.getenv("OS_HOST",   "localhost")
OS_PORT   = int(os.getenv("OS_PORT",  "19200"))
OS_INDEX  = os.getenv("OS_INDEX",  "practices_sessions")
CERT_FILE = os.getenv("TLS_CERT",  "secretos/admin/admin.crt")
KEY_FILE  = os.getenv("TLS_KEY",   "secretos/admin/admin_private.key")

COLUMNS = [
    "partner", "email", "user", "tenant",
    "fecha_inicio", "fecha_fin", "last_seen", "duracion_h",
]


def _os_ctx():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    ctx.load_cert_chain(CERT_FILE, KEY_FILE)
    return ctx


def download_sessions(size: int = 1000) -> list[dict]:
    ctx = _os_ctx()
    req = urllib.request.Request(
        f"https://{OS_HOST}:{OS_PORT}/{OS_INDEX}/_search?size={size}",
        method="GET",
    )
    with urllib.request.urlopen(req, context=ctx) as r:
        data = json.loads(r.read())
    return [h["_source"] for h in data["hits"]["hits"]]


def _duration_h(inicio: str, last_seen: str) -> float | None:
    fmt = "%Y-%m-%d %H:%M:%S"
    try:
        delta = datetime.strptime(last_seen, fmt) - datetime.strptime(inicio, fmt)
        return round(max(delta.total_seconds(), 0) / 3600, 2)
    except Exception:
        return None


def sessions_to_rows(sessions: list[dict]) -> list[dict]:
    rows = []
    for s in sessions:
        rows.append({
            "partner":      s.get("partner", ""),
            "email":        s.get("email", ""),
            "user":         s.get("user", ""),
            "tenant":       s.get("tenant", ""),
            "fecha_inicio": s.get("fecha_inicio", ""),
            "fecha_fin":    s.get("fecha_fin", ""),
            "last_seen":    s.get("last_seen", ""),
            "duracion_h":   _duration_h(s.get("fecha_inicio", ""), s.get("last_seen", "")),
        })
    rows.sort(key=lambda r: (r["partner"], r["fecha_inicio"]))
    return rows


def save_csv(rows: list[dict], output_path: str) -> None:
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Descarga practices_sessions de OpenSearch a CSV")
    parser.add_argument("--output", default="reports/sesiones_practicas.csv",
                        help="Ruta CSV de salida")
    args = parser.parse_args()

    print(f"Conectando a https://{OS_HOST}:{OS_PORT}/{OS_INDEX}...")
    try:
        sessions = download_sessions()
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"  {len(sessions)} sesiones descargadas")
    rows = sessions_to_rows(sessions)
    save_csv(rows, args.output)
    print(f"  Guardado: {args.output}")


if __name__ == "__main__":
    main()
