"""MCP server — training reports read-only tools."""

from mcp.server.fastmcp import FastMCP
from . import tools

mcp = FastMCP("training-reports")


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
