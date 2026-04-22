"""
deploy/run_transforms.py — Ejecuta las transformaciones Spark SQL sobre Stratio.

Se ejecuta UNA SOLA VEZ (o cuando cambia el esquema) para construir las capas
semántica y reporting sobre los datos RAW ya cargados en HDFS.

Flujo:
  1. Conecta al cluster Spark vía livy (REST) o SparkSession local (--local)
  2. Registra las tablas externas RAW sobre HDFS
  3. Ejecuta los SQL de src/transform/semantic/ en orden de dependencia
  4. Ejecuta los SQL de src/transform/reporting/ en orden de dependencia
  5. Imprime resumen de tablas creadas / errores

Uso:
  python3 src/deploy/run_transforms.py --help
  python3 src/deploy/run_transforms.py --dry-run          # solo imprime SQL
  python3 src/deploy/run_transforms.py --only semantic    # solo capa semántica
  python3 src/deploy/run_transforms.py --only reporting   # solo capa reporting
  python3 src/deploy/run_transforms.py --table f_usuarios # solo una tabla

Prerequisito:
  pip install pyspark  (no incluido en pyproject.toml porque Stratio provee su propia
  distribución de Spark; se conecta al cluster existente o se usa SparkSession local
  para validación).
"""

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.shared.utils import load_env, log

TRANSFORM_DIR = Path(__file__).parent.parent / "transform"

OK   = "\033[92m✓\033[0m"
FAIL = "\033[91m✗\033[0m"
WARN = "\033[93m⚠\033[0m"
INFO = "\033[94m·\033[0m"

# Orden de ejecución: las tablas que son JOIN de otras van después
SEMANTIC_ORDER = [
    "dim_partners.sql",
    "dim_cohortes.sql",
    "dim_cursos.sql",
    "f_usuarios.sql",       # depende de raw.users
    "f_inscripciones.sql",  # depende de f_usuarios, dim_cohortes
    "f_certificaciones.sql",# depende de f_usuarios, dim_cursos
    "f_actividad.sql",      # depende de f_usuarios
    "f_dedicacion.sql",     # depende de f_usuarios
]

REPORTING_ORDER = [
    "r_resumen_partner.sql",
    "r_evolucion_mensual.sql",
    "r_partner_categoria.sql",
    "r_partner_version.sql",
    "r_detalle_certificados.sql",
    "r_alertas.sql",
]

# Tablas RAW que Spark debe conocer como vistas externas sobre HDFS Parquet
RAW_TABLES = [
    "users",
    "courses",
    "cohorts",
    "cohort_members",
    "user_courses",
    "user_grades",
    "course_completions",
    "cohort_members_ext",
    "attendance_sessions",
    "enrol_cohort_course",
]


def build_raw_ddl(hdfs_base: str) -> list[str]:
    """Genera los CREATE EXTERNAL TABLE para registrar las tablas RAW en Spark."""
    stmts = []
    for table in RAW_TABLES:
        stmts.append(f"""
CREATE DATABASE IF NOT EXISTS raw
""".strip())
        stmts.append(f"""
CREATE TABLE IF NOT EXISTS raw.{table}
USING PARQUET
OPTIONS (path '{hdfs_base}/{table}/')
""".strip())
    stmts.append("CREATE DATABASE IF NOT EXISTS semantic")
    stmts.append("CREATE DATABASE IF NOT EXISTS reporting")
    return stmts


def load_sql(layer: str, filename: str) -> str:
    path = TRANSFORM_DIR / layer / filename
    if not path.exists():
        raise FileNotFoundError(f"SQL no encontrado: {path}")
    return path.read_text()


def run_spark(spark, statements: list[str], dry_run: bool) -> tuple[int, int]:
    ok = err = 0
    for sql in statements:
        sql = sql.strip()
        if not sql:
            continue
        preview = sql[:80].replace("\n", " ")
        if dry_run:
            print(f"  {INFO}  [DRY RUN] {preview}...")
            ok += 1
            continue
        try:
            spark.sql(sql)
            log(f"{preview}...", "✓")
            ok += 1
        except Exception as e:
            log(f"{preview}... ERROR: {e}", FAIL)
            err += 1
    return ok, err


def main():
    parser = argparse.ArgumentParser(
        description="Ejecuta transformaciones Spark SQL (semántica + reporting)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Imprime los SQL sin ejecutar nada."
    )
    parser.add_argument(
        "--only", choices=["semantic", "reporting"],
        help="Ejecuta solo una de las dos capas."
    )
    parser.add_argument(
        "--table", metavar="NOMBRE",
        help="Ejecuta solo el fichero SQL correspondiente a esta tabla (ej: f_usuarios)."
    )
    parser.add_argument(
        "--local", action="store_true",
        help="Usa SparkSession local (para pruebas sin cluster)."
    )
    args = parser.parse_args()

    load_env()
    hdfs_base = os.environ.get("HDFS_BASE_PATH", "/informes/moodle")

    print("\n" + "═" * 60)
    print("  Transformaciones Spark SQL")
    if args.dry_run:
        print("  [DRY RUN — no se ejecuta nada]")
    print("═" * 60 + "\n")

    # ── SparkSession ──────────────────────────────────────────────────────────
    spark = None
    if not args.dry_run:
        try:
            from pyspark.sql import SparkSession
        except ImportError:
            print(f"\n  {FAIL}  pyspark no instalado.")
            print("       pip install pyspark")
            print("       (En Stratio, usar el Spark del cluster — no instalar pyspark local)")
            sys.exit(1)
        builder = SparkSession.builder.appName("training-reports-transforms")
        if args.local:
            builder = builder.master("local[*]")
        spark = builder.getOrCreate()
        log("SparkSession iniciada", "✓")

    total_ok = total_err = 0

    # ── Registrar tablas RAW ──────────────────────────────────────────────────
    raw_ddl = build_raw_ddl(hdfs_base)
    log(f"Registrando {len(RAW_TABLES)} tablas RAW + schemas")
    ok, err = run_spark(spark, raw_ddl, args.dry_run)
    total_ok += ok; total_err += err

    # ── Selección de SQL a ejecutar ───────────────────────────────────────────
    def should_run(layer: str, filename: str) -> bool:
        if args.table:
            return filename == f"{args.table}.sql"
        if args.only:
            return layer == args.only
        return True

    # ── Semántica ─────────────────────────────────────────────────────────────
    if not args.only or args.only == "semantic":
        print(f"\n  {INFO}  Capa semántica")
        for fname in SEMANTIC_ORDER:
            if not should_run("semantic", fname):
                continue
            sql = load_sql("semantic", fname)
            table = fname.replace(".sql", "")
            log(f"semantic.{table}")
            ok, err = run_spark(spark, [sql], args.dry_run)
            total_ok += ok; total_err += err

    # ── Reporting ─────────────────────────────────────────────────────────────
    if not args.only or args.only == "reporting":
        print(f"\n  {INFO}  Capa reporting")
        for fname in REPORTING_ORDER:
            if not should_run("reporting", fname):
                continue
            sql = load_sql("reporting", fname)
            table = fname.replace(".sql", "")
            log(f"reporting.{table}")
            ok, err = run_spark(spark, [sql], args.dry_run)
            total_ok += ok; total_err += err

    # ── Resumen ───────────────────────────────────────────────────────────────
    print(f"\n  {'═' * 56}")
    if total_err == 0:
        print(f"  {OK}  Completado — {total_ok} sentencias ejecutadas")
    else:
        print(f"  {WARN}  Completado con errores — {total_ok} OK / {total_err} fallidas")
    print()

    return 1 if total_err else 0


if __name__ == "__main__":
    sys.exit(main())
