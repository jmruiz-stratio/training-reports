import json
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

from skill.analytics import partner_kpis
from python_core.config import load_settings
from python_core.validation.sanity import run as validate_snapshot, compare_snapshot_counts


# ── Audit log ─────────────────────────────────────────────────────────────────

def _log(accion: str, datos: dict) -> None:
    """Añade una línea al log de auditoría en AGENT_WORKDIR/log_reports.jsonl."""
    try:
        settings = load_settings()
        log_path = Path(settings.workdir) / "log_reports.jsonl"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "ts":     datetime.now(timezone.utc).isoformat(),
            "accion": accion,
            **datos,
        }
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
    except Exception:
        pass  # el log nunca rompe el flujo principal


# ── Auth ──────────────────────────────────────────────────────────────────────

def check_auth() -> dict:
    """Verifica el token de Moodle. Devuelve status ok/error con info del sitio."""
    settings = load_settings()
    if not settings.moodle_url or not settings.moodle_token:
        return {"status": "error", "error": "MOODLE_URL o MOODLE_TOKEN no definidos en .env"}

    url    = f"{settings.moodle_url}/webservice/rest/server.php"
    params = urllib.parse.urlencode({
        "wstoken":          settings.moodle_token,
        "wsfunction":       "core_webservice_get_site_info",
        "moodlewsrestformat": "json",
    }).encode()
    try:
        with urllib.request.urlopen(url, data=params, timeout=10) as r:
            data = json.loads(r.read())
        if "exception" in data:
            msg = data.get("message", "token inválido")
            _log("check_auth", {"status": "error", "error": msg})
            return {"status": "error", "error": msg}
        result = {
            "status":     "ok",
            "moodle_url": settings.moodle_url,
            "site":       data.get("sitename", ""),
            "username":   data.get("username", ""),
        }
        _log("check_auth", result)
        return result
    except Exception as e:
        _log("check_auth", {"status": "error", "error": str(e)})
        return {"status": "error", "error": str(e)}


# ── Snapshot ──────────────────────────────────────────────────────────────────

def get_latest_snapshot() -> dict:
    """Devuelve la ruta y metadata del snapshot más reciente en AGENT_WORKDIR."""
    settings = load_settings()
    base = Path(settings.workdir)
    if not base.exists():
        return {"status": "no_snapshots", "workdir": str(base)}

    dirs = sorted(
        [d for d in base.iterdir() if d.is_dir() and d.name[:4].isdigit()],
        reverse=True,
    )
    if not dirs:
        return {"status": "no_snapshots", "workdir": str(base)}

    latest   = dirs[0]
    datasets = sorted(f.stem for f in latest.glob("*.parquet"))
    sizes    = {f.stem: round(f.stat().st_size / 1024, 1) for f in latest.glob("*.parquet")}
    return {
        "status":   "ok",
        "snapshot": str(latest),
        "date":     latest.name,
        "datasets": datasets,
        "sizes_kb": sizes,
    }


# ── Ingesta ───────────────────────────────────────────────────────────────────

def run_ingest(date_str: str | None = None) -> dict:
    """
    Lanza la ingesta diaria desde Moodle.
    date_str: fecha en formato YYYY-MM-DD (default: hoy).
    """
    from batch_agent.runner import ingest_daily
    d = date.fromisoformat(date_str) if date_str else date.today()
    result = ingest_daily(d)
    _log("ingest", {"date": d.isoformat(), "workdir": result.get("workdir"), "datasets": list(result.get("checksums", {}).keys())})
    return result


# ── Compliance ────────────────────────────────────────────────────────────────

def run_compliance(
    workdir: str,
    course_pattern: str,
    empleados_xlsx: str | None = None,
    output_excel: str | None = None,
) -> dict:
    """
    Genera el informe de cumplimiento para un curso interno.
    Devuelve ruta del Excel + stats (completados, pendientes, sin_inscribir).
    """
    from skill.analytics import internal_course_compliance
    safe = course_pattern.replace(" ", "_").replace("/", "_")
    if output_excel is None:
        output_excel = f"reports/compliance_{safe}.xlsx"
    result = internal_course_compliance(
        workdir,
        course_pattern,
        output_excel=output_excel,
        empleados_xlsx=empleados_xlsx,
    )
    _log("compliance", {
        "course_pattern": course_pattern,
        "workdir":        workdir,
        "completados":    result.get("completados"),
        "pendientes":     result.get("pendientes"),
        "sin_inscribir":  result.get("sin_inscribir"),
        "excel":          result.get("excel"),
    })
    return result


# ── Export reporting ─────────────────────────────────────────────────────────

def run_export(
    workdir: str,
    partner: str | None = None,
    output_excel: str | None = None,
    practices_csv: str | None = None,
) -> dict:
    """
    Genera el Excel completo de reporting (todas las hojas) a partir de un snapshot.
    workdir: ruta al snapshot (ej: /tmp/moodle-reports-agent/2026-05-25).
    partner: filtrar por un partner concreto (opcional).
    """
    from skill.analytics import export_reporting_package
    d = Path(workdir).name
    if output_excel is None:
        suffix = f"_{partner}" if partner else ""
        output_excel = f"reports/informe_formacion_{d}{suffix}.xlsx"
    result = export_reporting_package(
        workdir,
        output_excel=output_excel,
        output_csv_dir=f"reports/csv_{d}",
        partner=partner or None,
        practices_csv=practices_csv,
    )
    _log("export", {
        "workdir":  workdir,
        "partner":  partner,
        "excel":    result.get("excel"),
        "sheets":   result.get("sheets"),
    })
    return result


# ── Audit log query ───────────────────────────────────────────────────────────

def get_audit_log(limit: int = 20) -> list[dict]:
    """Devuelve las últimas N entradas del log de auditoría."""
    settings = load_settings()
    log_path = Path(settings.workdir) / "log_reports.jsonl"
    if not log_path.exists():
        return []
    with open(log_path, encoding="utf-8") as f:
        lines = [l.strip() for l in f if l.strip()]
    entries = []
    for line in lines[-limit:]:
        try:
            entries.append(json.loads(line))
        except Exception:
            pass
    return entries


# ── Reglas de negocio ─────────────────────────────────────────────────────────

def get_business_rules() -> dict:
    """Devuelve las reglas de negocio activas (partner, certificación, categorías, validación)."""
    import yaml  # type: ignore
    rules_path = Path(__file__).parent.parent / "config" / "business_rules.yaml"
    if not rules_path.exists():
        return {"error": "config/business_rules.yaml no encontrado"}
    with open(rules_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


# ── Consultas existentes ──────────────────────────────────────────────────────

def list_training_partners(workdir: str) -> list[str]:
    return [r["partner"] for r in partner_kpis(workdir)]


def get_partner_kpis(workdir: str, partner: str) -> dict:
    for row in partner_kpis(workdir):
        if row["partner"] == partner:
            return row
    return {"partner": partner, "users": 0}


def validate_latest_snapshot(workdir: str) -> dict:
    return validate_snapshot(workdir)


def compare_snapshots(base_dir: str, target_dir: str) -> list[dict]:
    datasets = ["users", "courses", "cohorts", "user_grades"]
    return compare_snapshot_counts(base_dir, target_dir, datasets)
