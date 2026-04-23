import argparse
import json
from .analytics import partner_kpis, export_partner_kpis_csv, export_reporting_package


def main() -> int:
    p = argparse.ArgumentParser(description="Skill analytics CLI")
    sp = p.add_subparsers(dest="cmd", required=True)
    k = sp.add_parser("kpis")
    k.add_argument("workdir")

    e = sp.add_parser("export")
    e.add_argument("workdir")
    e.add_argument("output_csv")

    r = sp.add_parser("reporting")
    r.add_argument("workdir")
    r.add_argument("--output-excel", default="/tmp/reports_local/informe_formacion.xlsx")
    r.add_argument("--output-csv-dir", default="/tmp/reports_local/csv")
    r.add_argument("--partner", default=None)

    args = p.parse_args()
    if args.cmd == "kpis":
        print(json.dumps(partner_kpis(args.workdir), indent=2, ensure_ascii=False))
    elif args.cmd == "export":
        print(export_partner_kpis_csv(args.workdir, args.output_csv))
    else:
        result = export_reporting_package(
            args.workdir,
            output_excel=args.output_excel,
            output_csv_dir=args.output_csv_dir,
            partner=args.partner,
        )
        print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
