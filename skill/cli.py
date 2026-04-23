import argparse
import json
from .analytics import partner_kpis, export_partner_kpis_csv


def main() -> int:
    p = argparse.ArgumentParser(description="Skill analytics CLI")
    sp = p.add_subparsers(dest="cmd", required=True)
    k = sp.add_parser("kpis")
    k.add_argument("workdir")

    e = sp.add_parser("export")
    e.add_argument("workdir")
    e.add_argument("output_csv")

    args = p.parse_args()
    if args.cmd == "kpis":
        print(json.dumps(partner_kpis(args.workdir), indent=2, ensure_ascii=False))
    else:
        print(export_partner_kpis_csv(args.workdir, args.output_csv))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
