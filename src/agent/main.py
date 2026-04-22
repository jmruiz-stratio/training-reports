"""
agent/main.py — Punto de entrada del agente de ingesta RAW.

Flujo (§9.2 del CLAUDE.md):
  1. Valida variables de entorno
  2. Extrae cada dataset de Moodle
  3. Serializa a Parquet local
  4. Valida row counts + checksums
  5. Ejecuta sanity checks de negocio (DuckDB)
  6. Sube a HDFS vía Rocket
  7. Verifica presencia en HDFS
  8. Limpia la partición anterior
  9. Imprime resumen

Uso:
  python3 -m src.agent.main [--date YYYY-MM-DD] [--dry-run] [--skip-upload]
"""

import argparse
import os
import sys
from datetime import date, datetime

# Raíz del repo y src/ al path (los módulos internos usan 'from shared.xxx import ...')
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, "src"))

from src.agent import config
from src.agent.extract import run_all
from src.agent.to_parquet import write as write_parquet, row_count_local
from src.agent.validate import validate_dataset, assert_hdfs_present
from src.agent.sanity import run as run_sanity
from src.agent import upload_hdfs
from src.shared.utils import log

OK   = "\033[92m✓\033[0m"
FAIL = "\033[91m✗\033[0m"
WARN = "\033[93m⚠\033[0m"
INFO = "\033[94m·\033[0m"


def check_env() -> None:
    missing = []
    if not config.MOODLE_URL:
        missing.append("MOODLE_URL")
    if not config.MOODLE_TOKEN:
        missing.append("MOODLE_TOKEN")
    if not config.ROCKET_URL:
        missing.append("STRATIO_URL")
    if missing:
        print(f"\n  {FAIL}  Variables de entorno no definidas: {', '.join(missing)}")
        print("       Copia .env.example a .env y rellena los valores.")
        sys.exit(1)


def get_rocket_cookies() -> dict:
    """
    Obtiene las cookies de autenticación para Rocket (tenant formacion).

    Prioridad:
      1. STRATIO_COOKIE + JSESSIONID en .env  (valores individuales)
      2. PRACTICES_COOKIES_FORMACION en .env  (string completo de training-agents)
    """
    # Opción 1: variables individuales
    cookie    = os.environ.get("STRATIO_COOKIE", "").strip()
    jsession  = os.environ.get("JSESSIONID", "").strip()
    if cookie and jsession:
        return {"stratio-cookie": cookie, "JSESSIONID": jsession}

    # Opción 2: string completo formato "key=val; key=val" (PRACTICES_COOKIES_FORMACION)
    raw = os.environ.get("PRACTICES_COOKIES_FORMACION", "").strip()
    if raw:
        parts = {}
        for part in raw.split(";"):
            part = part.strip()
            if "=" in part:
                k, _, v = part.partition("=")
                parts[k.strip()] = v.strip()
        sc = parts.get("stratio-cookie", "")
        js = parts.get("JSESSIONID", "")
        if sc and js:
            return {"stratio-cookie": sc, "JSESSIONID": js}

    # Opción 3: login automático con las credenciales del .env
    rocket_url = config.ROCKET_URL
    user       = config.STRATIO_USER
    password   = config.STRATIO_PASS
    tenant     = config.STRATIO_TENANT

    if user and password:
        log("Cookies no encontradas en .env, intentando login automático...")
        try:
            from src.shared.practices_auth import get_cookies
            return get_cookies(rocket_url, user, password, tenant)
        except RuntimeError as e:
            log(f"Login automático fallido: {e}", "⚠")
            log("Regenera las cookies con: python3 src/refresh_cookies.py", "⚠")

    print(f"\n  {FAIL}  Cookies de Rocket no disponibles.")
    print("       Ejecuta:  python3 src/refresh_cookies.py")
    sys.exit(1)


def previous_partition(dataset: str, ingest_date: date,
                       rocket_url: str, cookies: dict) -> str | None:
    """
    Devuelve la ruta de la partición anterior a ingest_date si existe,
    o None si no hay ninguna.
    """
    dataset_dir = f"{config.HDFS_BASE_PATH}/{dataset}"
    try:
        items = upload_hdfs.list_path(dataset_dir, rocket_url, cookies)
    except Exception:
        return None
    today_partition = f"ingest_date={ingest_date.isoformat()}"
    for item in items:
        name = item.get("name", "").rstrip("/").split("/")[-1]
        if name.startswith("ingest_date=") and name != today_partition:
            return item["name"]
    return None


def main(ingest_date: date, dry_run: bool, skip_upload: bool) -> int:
    print("\n" + "═" * 60)
    print(f"  Agente RAW — {ingest_date.isoformat()}")
    if dry_run:
        print("  [DRY RUN — no se sube nada a HDFS]")
    print("═" * 60 + "\n")

    check_env()

    workdir = os.path.join(config.WORKDIR, ingest_date.isoformat())
    os.makedirs(workdir, exist_ok=True)
    log(f"Workdir: {workdir}")

    # ── 1. Extracción ─────────────────────────────────────────────────────────
    print(f"\n  {INFO}  Extracción Moodle")
    datasets_data = run_all(
        config.MOODLE_URL,
        config.MOODLE_TOKEN,
        config.DATASETS_ALL,
    )

    # ── 2. Serialización a Parquet + validación técnica ───────────────────────
    print(f"\n  {INFO}  Serialización y validación técnica")
    checksums: dict[str, str] = {}
    parquet_paths: dict[str, str] = {}

    for dataset, rows in datasets_data.items():
        if not rows:
            log(f"{dataset}: 0 filas, omitido", WARN)
            continue
        path = write_parquet(rows, dataset, workdir)
        cs = validate_dataset(rows, path, dataset)
        checksums[dataset] = cs
        parquet_paths[dataset] = path

    # ── 3. Sanity checks de negocio ───────────────────────────────────────────
    print(f"\n  {INFO}  Sanity checks de negocio")
    kpis = run_sanity(workdir)

    if dry_run or skip_upload:
        print(f"\n  {WARN}  Subida omitida (--dry-run / --skip-upload)\n")
        return 0

    # ── 4. Subida a HDFS ──────────────────────────────────────────────────────
    print(f"\n  {INFO}  Subida a HDFS")
    cookies = get_rocket_cookies()
    uploaded: list[str] = []
    prev_partitions: dict[str, str | None] = {}

    for dataset, path in parquet_paths.items():
        hdfs_dir = upload_hdfs.partition_path(dataset, ingest_date, config.HDFS_BASE_PATH)
        filename  = os.path.basename(path)

        # Guarda la partición anterior antes de subir la nueva
        prev_partitions[dataset] = previous_partition(
            dataset, ingest_date, config.ROCKET_URL, cookies
        )

        log(f"Subiendo {dataset} → {hdfs_dir}/")
        upload_hdfs.put(path, hdfs_dir, config.ROCKET_URL, cookies)

        # Verifica que llegó correctamente
        items = upload_hdfs.list_path(hdfs_dir, config.ROCKET_URL, cookies)
        assert_hdfs_present(items, filename, dataset)
        uploaded.append(dataset)

    # ── 5. Limpieza de particiones anteriores ─────────────────────────────────
    # Solo si TODOS los datasets subieron correctamente
    if len(uploaded) == len(parquet_paths):
        print(f"\n  {INFO}  Limpieza de particiones anteriores")
        for dataset, prev_path in prev_partitions.items():
            if prev_path:
                try:
                    upload_hdfs.delete_partition(prev_path, config.ROCKET_URL, cookies)
                    log(f"Borrada partición anterior: {prev_path}", "✓")
                except NotImplementedError:
                    log(f"Borrado pendiente de implementar para: {prev_path}", WARN)
                except Exception as e:
                    log(f"No se pudo borrar {prev_path}: {e}", WARN)
    else:
        log(f"No se limpian particiones anteriores: solo subieron "
            f"{len(uploaded)}/{len(parquet_paths)} datasets", WARN)

    # ── 6. Resumen ────────────────────────────────────────────────────────────
    print(f"\n  {'═' * 56}")
    print(f"  {OK}  Ingesta completada — {ingest_date.isoformat()}")
    print(f"     Datasets subidos:  {len(uploaded)}")
    print(f"     Partners:          {kpis.get('n_partners', '?')}")
    print(f"     Usuarios:          {kpis.get('total_users', '?')}")
    print(f"     Cohortes:          {kpis.get('total_cohorts', '?')}")
    print(f"     Cursos:            {kpis.get('total_courses', '?')}")
    print(f"     Certificaciones:   {kpis.get('certificaciones_aprobadas', '?')}")
    print()

    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Agente de ingesta RAW Moodle → HDFS")
    parser.add_argument(
        "--date",
        default=date.today().isoformat(),
        help="Fecha de ingesta (YYYY-MM-DD). Por defecto: hoy.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Extrae y valida pero no sube a HDFS.",
    )
    parser.add_argument(
        "--skip-upload",
        action="store_true",
        help="Igual que --dry-run pero más explícito.",
    )
    args = parser.parse_args()

    ingest_date = date.fromisoformat(args.date)
    sys.exit(main(ingest_date, args.dry_run, args.skip_upload))
