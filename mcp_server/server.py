"""Minimal MCP-like dispatcher for high-level read-only tools (v1)."""

import json
from . import tools

TOOL_MAP = {
    "list_training_partners": tools.list_training_partners,
    "get_partner_kpis": tools.get_partner_kpis,
    "validate_latest_snapshot": tools.validate_latest_snapshot,
    "compare_snapshots": tools.compare_snapshots,
}


def dispatch(tool: str, **kwargs):
    if tool not in TOOL_MAP:
        raise ValueError(f"Unknown tool: {tool}")
    return TOOL_MAP[tool](**kwargs)


def main() -> int:
    # stdin json lines: {"tool":"...", "args":{...}}
    import sys
    for line in sys.stdin:
        req = json.loads(line)
        result = dispatch(req["tool"], **req.get("args", {}))
        print(json.dumps({"ok": True, "result": result}, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
