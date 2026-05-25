"""MCP server — training reports tools."""

from mcp.server.fastmcp import FastMCP
from . import tools

mcp = FastMCP("training-reports")


# ── Auth & estado ─────────────────────────────────────────────────────────────

@mcp.tool()
def check_auth() -> dict:
    """Verifica el token de Moodle. Devuelve status ok/error con info del sitio."""
    return tools.check_auth()


@mcp.tool()
def get_latest_snapshot() -> dict:
    """Devuelve ruta, fecha y datasets del snapshot más reciente en AGENT_WORKDIR."""
    return tools.get_latest_snapshot()


# ── Ingesta ───────────────────────────────────────────────────────────────────

@mcp.tool()
def run_ingest(date_str: str = "") -> dict:
    """
    Lanza la ingesta diaria desde Moodle y guarda los Parquet locales.
    date_str: fecha YYYY-MM-DD (vacío = hoy).
    """
    return tools.run_ingest(date_str or None)


# ── Compliance ────────────────────────────────────────────────────────────────

@mcp.tool()
def run_compliance(
    workdir: str,
    course_pattern: str,
    empleados_xlsx: str = "",
    output_excel: str = "",
) -> dict:
    """
    Genera el informe de cumplimiento para un curso interno de Stratio.
    workdir: ruta al snapshot (ej: /tmp/moodle-reports-agent/2026-05-25).
    course_pattern: texto a buscar en el nombre del curso (ej: 'blanqueo').
    empleados_xlsx: ruta al Excel de empleados para cruzar (opcional).
    output_excel: ruta de salida del Excel (opcional).
    """
    return tools.run_compliance(
        workdir,
        course_pattern,
        empleados_xlsx=empleados_xlsx or None,
        output_excel=output_excel or None,
    )


# ── Export reporting ─────────────────────────────────────────────────────────

@mcp.tool()
def run_export(
    workdir: str,
    partner: str = "",
    output_excel: str = "",
    practices_csv: str = "",
) -> dict:
    """
    Genera el Excel completo de reporting (todas las hojas) a partir de un snapshot.
    workdir: ruta al snapshot (ej: /tmp/moodle-reports-agent/2026-05-25).
    partner: filtrar por un partner concreto (opcional).
    practices_csv: ruta al CSV de prácticas para enriquecer el informe (opcional).
    """
    return tools.run_export(
        workdir,
        partner=partner or None,
        output_excel=output_excel or None,
        practices_csv=practices_csv or None,
    )


# ── Audit log ─────────────────────────────────────────────────────────────────

@mcp.tool()
def get_audit_log(limit: int = 20) -> list[dict]:
    """Devuelve las últimas N entradas del log de auditoría (AGENT_WORKDIR/log_reports.jsonl)."""
    return tools.get_audit_log(limit)


# ── Reglas de negocio ─────────────────────────────────────────────────────────

@mcp.tool()
def get_business_rules() -> dict:
    """Devuelve las reglas de negocio activas (partner, certificación, categorías, validación)."""
    return tools.get_business_rules()


# ── Consultas ─────────────────────────────────────────────────────────────────

@mcp.tool()
def list_training_partners(workdir: str) -> list[str]:
    """Lista todos los partners con usuarios en el snapshot indicado."""
    return tools.list_training_partners(workdir)


@mcp.tool()
def get_partner_kpis(workdir: str, partner: str) -> dict:
    """Devuelve KPIs (usuarios, certificaciones) de un partner concreto."""
    return tools.get_partner_kpis(workdir, partner)


@mcp.tool()
def validate_latest_snapshot(workdir: str) -> dict:
    """Valida un snapshot: row counts y KPIs básicos de negocio."""
    return tools.validate_latest_snapshot(workdir)


@mcp.tool()
def compare_snapshots(base_dir: str, target_dir: str) -> list[dict]:
    """Compara row counts entre dos snapshots y devuelve los deltas por dataset."""
    return tools.compare_snapshots(base_dir, target_dir)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
